FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Build context is the repository root. Copy application files explicitly so
# private runtime configuration never enters the image or its build layers.
COPY backend/app ./backend/app
COPY backend/__init__.py ./backend/__init__.py
COPY backend/alembic.ini ./backend/alembic.ini
COPY backend/migrations ./backend/migrations
COPY backend/scripts/migrate.py ./backend/scripts/migrate.py
COPY backend/ctf-flags.example.json ./backend/ctf-flags.example.json

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
