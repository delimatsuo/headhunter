#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.local.yml"
PSQL_FILE="/docker-entrypoint-initdb.d/01-init.sql"
POSTGRES_CONTAINER="hh-local-postgres"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command is required" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 command is required" >&2
  exit 1
fi

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Missing ${COMPOSE_FILE}. Run from repository root." >&2
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -q "${POSTGRES_CONTAINER}"; then
  echo "Postgres container ${POSTGRES_CONTAINER} is not running." >&2
  exit 1
fi

echo "Replaying SQL seed script against Postgres..."
docker exec "${POSTGRES_CONTAINER}" psql -U headhunter -d headhunter -f "${PSQL_FILE}" >/dev/null

echo "Seeding Firestore emulator collections..."
export FIREBASE_PROJECT_ID="${FIREBASE_PROJECT_ID:-headhunter-local}"
export FIRESTORE_EMULATOR_HOST="${FIRESTORE_EMULATOR_HOST:-localhost:8080}"
python3 "${SCRIPT_DIR}/seed_firestore.py"

echo "Seed datasets refreshed successfully."
