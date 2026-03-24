#!/bin/sh
set -e

echo "Running database migrations..."
business-use db migrate

echo "Starting server on port 13370 with ${WORKERS:-4} workers..."
exec business-use server prod --host 0.0.0.0 --port 13370 --workers "${WORKERS:-4}"
