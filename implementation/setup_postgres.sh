#!/bin/bash
# PostgreSQL Setup Script for PANCAKE POC
# This script sets up the databases and optionally tries to install pgvector

set -e  # Exit on error

echo "=================================================="
echo "PANCAKE POC - PostgreSQL Setup"
echo "=================================================="
echo ""

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL not found!"
    echo "Please install PostgreSQL first:"
    echo "  macOS:  brew install postgresql@15"
    echo "  Ubuntu: sudo apt install postgresql"
    exit 1
fi

echo "✓ PostgreSQL found: $(psql --version)"
echo ""

# Check if PostgreSQL is running
if ! pg_isready &> /dev/null; then
    echo "⚠️  PostgreSQL is not running!"
    echo "Starting PostgreSQL..."
    
    # Try to start PostgreSQL (macOS)
    if command -v brew &> /dev/null; then
        brew services start postgresql@15 || brew services start postgresql || true
        sleep 2
    fi
    
    # Check again
    if ! pg_isready &> /dev/null; then
        echo "❌ Failed to start PostgreSQL"
        echo "Please start it manually:"
        echo "  macOS:  brew services start postgresql@15"
        echo "  Linux:  sudo systemctl start postgresql"
        exit 1
    fi
fi

echo "✓ PostgreSQL is running"
echo ""

# Create user
echo "Creating database user 'pancake_user'..."
psql postgres -c "CREATE USER pancake_user WITH PASSWORD 'pancake_pass';" 2>/dev/null || echo "  (User already exists)"
psql postgres -c "ALTER USER pancake_user CREATEDB;" 2>/dev/null

# Create databases
echo "Creating databases..."
psql postgres -c "CREATE DATABASE pancake_poc OWNER pancake_user;" 2>/dev/null || echo "  (pancake_poc already exists)"
psql postgres -c "CREATE DATABASE traditional_poc OWNER pancake_user;" 2>/dev/null || echo "  (traditional_poc already exists)"

# Grant privileges
echo "Granting privileges..."
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE pancake_poc TO pancake_user;" 2>/dev/null
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE traditional_poc TO pancake_user;" 2>/dev/null

echo ""
echo "✓ Database setup complete!"
echo ""

# Try to enable pgvector
echo "Attempting to enable pgvector extension..."
if psql -U pancake_user -d pancake_poc -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null; then
    echo "✓ pgvector extension enabled"
    PGVECTOR_STATUS="✓ Available"
else
    echo "⚠️  pgvector extension not available"
    echo "   The notebook will work without embeddings"
    PGVECTOR_STATUS="✗ Not available (optional)"
fi

echo ""
echo "=================================================="
echo "Setup Summary"
echo "=================================================="
echo "PostgreSQL:     ✓ Running"
echo "User:           ✓ pancake_user"
echo "Databases:      ✓ pancake_poc, traditional_poc"
echo "pgvector:       $PGVECTOR_STATUS"
echo ""

# Test connection
echo "Testing database connection..."
if psql -U pancake_user -d pancake_poc -c "SELECT 'Connection successful!' as status;" > /dev/null 2>&1; then
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

