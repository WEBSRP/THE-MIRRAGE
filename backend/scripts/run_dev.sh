#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)"
cd "$DIR"

if [ -d "backend/venv" ]; then
    source backend/venv/bin/activate
fi

if [ ! -f "backend/.env" ]; then
    echo "Creating backend/.env from backend/.env.example..."
    cp backend/.env.example backend/.env
fi

export PYTHONPATH=.
export ENVIRONMENT=development

echo "================================================="
echo " Starting MIRRAGE FastAPI Backend (Dev Mode)"
echo " Docs available at: http://localhost:8000/api/v1/docs"
echo "================================================="

uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
