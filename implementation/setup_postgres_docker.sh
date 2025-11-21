#!/bin/bash
# Docker-based PostgreSQL Setup Script for PANCAKE POC
# This script:
#   - checks Docker & version
#   - finds a free port in 15432–16432
#   - starts the pancake_postgres container via docker compose
#   - configures DBs, user, privileges, and pgvector inside the container

set -e  # Exit on error
IMAGE_NAME="pgvector/pgvector:pg16"

echo "=================================================="
echo "PANCAKE POC - PostgreSQL Setup (Dockerised)"
echo "=================================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/../pancake-postgres/docker-compose.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ docker-compose.yml not found at: $COMPOSE_FILE"
    echo "   Please check the path or move the file."
    exit 1
fi


# -----------------------------
# 1. Check Docker installation
# -----------------------------
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found!"
    echo "Please install Docker first."
    exit 1
fi

DOCKER_VERSION_RAW="$(docker --version | awk '{print $3}' | sed 's/,//')"
DOCKER_MAJOR="${DOCKER_VERSION_RAW%%.*}"

echo "✓ Docker found: $DOCKER_VERSION_RAW"

# Just warn if major version is below 29 (still allow running)
if [ "$DOCKER_MAJOR" -lt 29 ]; then
    echo "⚠️  Docker major version is < 29 (you have $DOCKER_VERSION_RAW)."
    echo "    It should still work, but target version is 29.0.2 (build 8108357) or newer."
fi
echo ""

# Ensure the pgvector image is available
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "PostgreSQL image $IMAGE_NAME not found locally. Pulling..."
    if ! docker pull "$IMAGE_NAME"; then
        echo "❌ Failed to pull Docker image: $IMAGE_NAME"
        exit 1
    fi
else
    echo "✓ Docker image $IMAGE_NAME already present locally"
fi
echo ""


# --------------------------------------------
# 2. Find a free port in range 15432–16432
# --------------------------------------------
find_free_port() {
    local port

    for port in $(seq 15432 16432); do
        # Use ss if available (modern), otherwise fall back to netstat
        if command -v ss &> /dev/null; then
            if ! ss -tln 2>/dev/null | awk '{print $4}' | grep -q ":$port$"; then
                echo "$port"
                return 0
            fi
        else
            if ! netstat -tln 2>/dev/null | awk '{print $4}' | grep -q ":$port$"; then
                echo "$port"
                return 0
            fi
        fi
    done

    # No free port found in the range
    return 1
}

echo "Selecting a free port for PostgreSQL (15432–16432)..."
HOST_PORT="$(find_free_port)" || {
    echo "❌ No free port found in range 15432–16432"
    exit 1
}
echo "✓ Using host port: $HOST_PORT"

# This env var is picked up by docker-compose.yml:
#   ports:
#     - "${POSTGRES_PORT:-15432}:5432"
export POSTGRES_PORT="$HOST_PORT"
echo ""

# Persist chosen port so Python / notebooks can read it later
PORT_FILE="$SCRIPT_DIR/../.pancake_db_port"
echo "$HOST_PORT" > "$PORT_FILE"
echo "Saved chosen port to $PORT_FILE"
echo ""

# --------------------------------------------------
# 3. Start the Postgres container via docker compose
# --------------------------------------------------
# NOTE:
#   Run this script from the directory where docker-compose.yml lives.
#   If not, add:  -f /path/to/docker-compose.yml
echo "Starting PostgreSQL container (pancake_postgres) with docker compose..."
if ! docker compose -f "$COMPOSE_FILE" up -d pancake_postgres; then
    echo "❌ Failed to start pancake_postgres via docker compose"
    exit 1
fi

echo "Waiting for PostgreSQL in container to be ready..."
# Poll pg_isready INSIDE the container until it's healthy
until docker exec pancake-postgres pg_isready -U pancake_user -d pancake_poc >/dev/null 2>&1; do
    sleep 2
done

echo "✓ PostgreSQL container is up and ready"
echo "   Host: localhost"
echo "   Port: $HOST_PORT"
echo "   Container: pancake-postgres"
echo ""

# ----------------------------------------
# 4. Configure user & databases (inside)
# ----------------------------------------
echo "Creating/ensuring database user 'pancake_user'..."
docker exec -i pancake-postgres psql -U pancake_user -d postgres -c \
  "DO \$\$
   BEGIN
     IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pancake_user') THEN
       CREATE ROLE pancake_user LOGIN PASSWORD 'pancake_pass' CREATEDB;
     ELSE
       ALTER ROLE pancake_user CREATEDB;
     END IF;
   END
   \$\$;" >/dev/null

echo "Creating databases..."
docker exec -i pancake-postgres psql -U pancake_user -d postgres -c \
  "CREATE DATABASE pancake_poc OWNER pancake_user;" 2>/dev/null || echo "  (pancake_poc already exists)"

docker exec -i pancake-postgres psql -U pancake_user -d postgres -c \
  "CREATE DATABASE traditional_poc OWNER pancake_user;" 2>/dev/null || echo "  (traditional_poc already exists)"

echo "Granting privileges..."
docker exec -i pancake-postgres psql -U pancake_user -d postgres -c \
  "GRANT ALL PRIVILEGES ON DATABASE pancake_poc TO pancake_user;" >/dev/null 2>&1

docker exec -i pancake-postgres psql -U pancake_user -d postgres -c \
  "GRANT ALL PRIVILEGES ON DATABASE traditional_poc TO pancake_user;" >/dev/null 2>&1

echo ""
echo "✓ Database setup inside container complete!"
echo ""

# -------------------------------
# 5. Enable pgvector (if present)
# -------------------------------
echo "Attempting to enable pgvector extension..."
if docker exec -i pancake-postgres psql -U pancake_user -d pancake_poc -c \
   "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null 2>&1; then
    echo "✓ pgvector extension enabled"
    PGVECTOR_STATUS="✓ Available"
else
    echo "⚠️  pgvector extension not available"
    echo "   The notebook will work without embeddings"
    PGVECTOR_STATUS="✗ Not available (optional)"
fi

echo ""
echo "=================================================="
echo "Setup Summary (Dockerised)"
echo "=================================================="
echo "PostgreSQL:     ✓ Running in container 'pancake-postgres'"
echo "Host:           localhost"
echo "Port:           $HOST_PORT"
echo "User:           ✓ pancake_user"
echo "Databases:      ✓ pancake_poc, traditional_poc"
echo "pgvector:       $PGVECTOR_STATUS"
echo ""

# -----------------------------
# 6. Final connection test
# -----------------------------
echo "Testing database connection to pancake_poc..."
if docker exec -i pancake-postgres psql -U pancake_user -d pancake_poc -c \
   "SELECT 'Connection successful!' as status;" > /dev/null 2>&1; then
    echo "✓ Connection test passed"
else
    echo "❌ Connection test failed"
    exit 1
fi

echo ""
echo "=================================================="
echo "✅ Setup complete! You can now run the notebook."
echo "=================================================="
echo ""
echo "Note: If pgvector is not available, the notebook will"
echo "automatically skip embedding-related operations."
echo ""
echo "To stop the database later:"
echo "  docker compose down"
echo ""
