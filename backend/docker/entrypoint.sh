#!/bin/sh
set -eu

DOCUMENT_STORAGE_DIR="${DOCUMENT_STORAGE_DIR:-/data/documents}"
mkdir -p "${DOCUMENT_STORAGE_DIR}"

echo "Aplicando migrações Alembic (upgrade head)..."
alembic upgrade head

echo "Iniciando FastAPI com 1 worker (sem --reload)..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips='*'
