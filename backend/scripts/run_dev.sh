#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Activate backend virtual environment
if [ -d "backend/.venv" ]; then
    source backend/.venv/bin/activate
else
    echo "ERROR: backend/.venv not found"
    exit 1
fi

# Create .env only if it doesn't exist
if [ ! -f "backend/.env" ]; then
    if [ -f "backend/.env.example" ]; then
        echo "Creating backend/.env from backend/.env.example..."
        cp backend/.env.example backend/.env
    else
        echo "ERROR: backend/.env.example not found"
        exit 1
    fi
fi

export PYTHONPATH=.
export ENVIRONMENT=development

echo "=================================================="
echo " Starting MIRRAGE FastAPI Backend"
echo "=================================================="
echo " API:  http://127.0.0.1:8000"
echo " Docs: http://127.0.0.1:8000/api/v1/docs"
echo " Public access: Nginx → FastAPI"
echo "=================================================="

# Run FastAPI
exec uvicorn backend.app.main:app \
    --host 127.0.0.1 \
    --port 8000
