#!/bin/bash
# Setup script for Pancake MVP

set -e

echo "=== Pancake MVP Setup ==="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment exists"
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Check PostgreSQL connection
echo "Checking PostgreSQL connection..."
if command -v psql &> /dev/null; then
    echo "✓ PostgreSQL client found"
else
    echo "⚠ PostgreSQL client not found - install with: brew install postgresql"
fi

# Create database (if not exists)
echo "Setting up database..."
# Note: Update DATABASE_URL in .env.example and copy to .env

# Run migrations
echo "Running database migrations..."
export FLASK_APP=app.py
flask db upgrade || echo "⚠ Migrations will be created after database is available"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and configure DATABASE_URL"
echo "2. Start PostgreSQL: docker compose up -d postgres (or use local PostgreSQL)"
echo "3. Run migrations: flask db upgrade"
echo "4. Start development server: python app.py"
echo ""

