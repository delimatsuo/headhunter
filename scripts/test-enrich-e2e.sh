#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for test-enrich-e2e.sh" >&2
  exit 1
fi

COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.local.yml}
STACK_NAME=${STACK_NAME:-headhunter-local}
SERVICE_URL=${ENRICH_URL:-http://localhost:7112}
EMBED_URL=${EMBED_URL:-http://localhost:7101}
FIRESTORE_HOST=${FIRESTORE_HOST:-http://localhost:8080}
TENANT_ID=${TENANT_ID:-tenant-alpha}
CANDIDATE_ID=${CANDIDATE_ID:-cand-e2e-$(date +%s)}
MAX_WAIT_SECONDS=${MAX_WAIT_SECONDS:-120}
ISSUER_URL=${ISSUER_URL:-http://localhost:8081}
SCOPES=${SCOPES:-embeddings:write search:read}

TOKEN=$(curl -sS -X POST -H 'Content-Type: application/json' \
  -d "{\"tenant_id\":\"${TENANT_ID}\",\"scope\":\"${SCOPES}\"}" \
  "${ISSUER_URL}/token" | jq -r '.access_token')

if [[ -z "${TOKEN}" || "${TOKEN}" == "null" ]]; then
  echo "[test-enrich-e2e] Failed to obtain access token from mock-oauth" >&2
  exit 1
fi

SERVICES=(redis firestore-emulator mock-oauth mock-together hh-embed-svc hh-enrich-svc)

echo "[test-enrich-e2e] Bringing up docker compose services: ${SERVICES[*]}"
docker compose -f "$COMPOSE_FILE" up -d "${SERVICES[@]}"

echo "[test-enrich-e2e] Waiting for enrichment service health endpoint"
for _ in {1..30}; do
  if curl -sf "$SERVICE_URL/health" >/dev/null; then
    break
  fi
  sleep 2
else
  echo "Enrichment service did not become healthy in time" >&2
  exit 1
fi

echo "[test-enrich-e2e] Seeding candidate ${CANDIDATE_ID} for tenant ${TENANT_ID}"
SEED_PAYLOAD=$(cat <<JSON
{
  "candidateId": "${CANDIDATE_ID}",
  "async": true,
  "payload": {
    "profile": {
      "resumeText": "Senior Software Engineer with strong TypeScript experience",
      "headline": "Test Candidate"
    }
  }
}
JSON
)

curl -sf -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Tenant-ID: ${TENANT_ID}" \
  -d "$SEED_PAYLOAD" \
  "$SERVICE_URL/v1/enrich/profile" > /tmp/enrich_job.json

JOB_ID=$(jq -r '.job.jobId' /tmp/enrich_job.json)
if [[ -z "$JOB_ID" || "$JOB_ID" == "null" ]]; then
  echo "Failed to submit enrichment job" >&2
  cat /tmp/enrich_job.json >&2
  exit 1
fi

echo "[test-enrich-e2e] Submitted job ${JOB_ID}. Polling for completion."
START_TIME=$(date +%s)
while true; do
  STATUS_RESPONSE=$(curl -sf \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-Tenant-ID: ${TENANT_ID}" \
    "$SERVICE_URL/v1/enrich/status/${JOB_ID}")
  JOB_STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.job.status // "unknown"')
  if [[ "$JOB_STATUS" == "completed" ]]; then
    echo "[test-enrich-e2e] Job completed"
    break
  fi
  if [[ "$JOB_STATUS" == "failed" ]]; then
    echo "Job failed:" >&2
    echo "$STATUS_RESPONSE" | jq '.' >&2
    exit 1
  fi
  if (( $(date +%s) - START_TIME > MAX_WAIT_SECONDS )); then
    echo "Job did not complete within ${MAX_WAIT_SECONDS}s" >&2
    exit 1
  fi
  sleep 3
done

echo "$STATUS_RESPONSE" | jq '.'

EMBEDDED=$(echo "$STATUS_RESPONSE" | jq -r '.job.result.embeddingUpserted')
if [[ "$EMBEDDED" != "true" ]]; then
  SKIP_REASON=$(echo "$STATUS_RESPONSE" | jq -r '.job.result.embeddingSkippedReason // "unknown"')
  echo "Warning: embedding upsert reported as failure (reason: ${SKIP_REASON})" >&2
fi

echo "[test-enrich-e2e] Checking Firestore emulator for candidate document"
DOCUMENT_PATH="projects/headhunter-local/databases/(default)/documents/candidates/${TENANT_ID}_${CANDIDATE_ID}"
FIRESTORE_RESPONSE=$(curl -sf "$FIRESTORE_HOST/v1/${DOCUMENT_PATH}" || true)
if [[ -n "$FIRESTORE_RESPONSE" ]]; then
  echo "$FIRESTORE_RESPONSE" | jq '.'
else
  echo "Firestore document not found; ensure seed processor populated emulator" >&2
fi

echo "[test-enrich-e2e] Pulling recent logs for enrichment job"
docker compose -f "$COMPOSE_FILE" logs --since 5m hh-enrich-svc | grep "$JOB_ID" || true

echo "[test-enrich-e2e] Test run complete"
