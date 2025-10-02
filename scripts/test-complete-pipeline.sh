#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Execute the full enrich -> embed -> search -> rerank -> evidence pipeline
# against a deployed environment.
#
# Usage:
#   ./scripts/test-complete-pipeline.sh [staging|production]

ENVIRONMENT="${1:-staging}"
if [[ "${ENVIRONMENT}" != "staging" && "${ENVIRONMENT}" != "production" ]]; then
  echo "Environment must be staging or production" >&2
  exit 1
fi

PROJECT_ID="${PROJECT_ID:-headhunter-${ENVIRONMENT}}"
REGION="${REGION:-us-central1}"
TENANT_ID="${TENANT_ID:-tenant-alpha}"
ISSUER_URL="${ISSUER_URL:-https://idp.${ENVIRONMENT}.ella.jobs}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud CLI is required" >&2
  exit 1
fi

fetch_service_url() {
  local service="$1"
  gcloud run services describe "${service}" \
    --platform=managed \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format='value(status.url)'
}

EMBED_URL="$(fetch_service_url "hh-embed-svc-${ENVIRONMENT}")"
SEARCH_URL="$(fetch_service_url "hh-search-svc-${ENVIRONMENT}")"
RERANK_URL="$(fetch_service_url "hh-rerank-svc-${ENVIRONMENT}")"
EVIDENCE_URL="$(fetch_service_url "hh-evidence-svc-${ENVIRONMENT}")"
ECO_URL="$(fetch_service_url "hh-eco-svc-${ENVIRONMENT}")"
ADMIN_URL="$(fetch_service_url "hh-admin-svc-${ENVIRONMENT}")"
MSGS_URL="$(fetch_service_url "hh-msgs-svc-${ENVIRONMENT}")"
ENRICH_URL="$(fetch_service_url "hh-enrich-svc-${ENVIRONMENT}")"

env \
  TENANT_ID="${TENANT_ID}" \
  ISSUER_URL="${ISSUER_URL}" \
  EMBED_BASE_URL="${EMBED_URL}" \
  SEARCH_BASE_URL="${SEARCH_URL}" \
  RERANK_BASE_URL="${RERANK_URL}" \
  EVIDENCE_BASE_URL="${EVIDENCE_URL}" \
  ECO_BASE_URL="${ECO_URL}" \
  ADMIN_BASE_URL="${ADMIN_URL}" \
  MSGS_BASE_URL="${MSGS_URL}" \
  ENRICH_BASE_URL="${ENRICH_URL}" \
  python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run_integration.py"
