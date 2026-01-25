#!/bin/bash
# Run embedding backfill worker
# Usage: ./scripts/run-embedding-backfill.sh [--dry-run]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment if .env exists
if [ -f "$PROJECT_ROOT/.env" ]; then
  export $(cat "$PROJECT_ROOT/.env" | grep -v '^#' | xargs)
fi

echo "Starting embedding backfill worker..."
echo "Database: ${PGVECTOR_HOST:-127.0.0.1}:${PGVECTOR_PORT:-5432}/${PGVECTOR_DATABASE:-headhunter}"

cd "$PROJECT_ROOT"
npx ts-node scripts/embedding-backfill-worker.ts "$@"
