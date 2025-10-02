#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Runs a series of smoke tests against a deployed hh-admin-svc instance. The
# script verifies the health endpoint, refresh orchestration endpoints, and the
# monitoring snapshot route. Provide SERVICE_URL and TENANT_ID. An identity token
# is fetched with gcloud by default, but ADMIN_BEARER can be supplied manually.

SERVICE_URL="${SERVICE_URL:-}"
TENANT_ID="${TENANT_ID:-}"
REQUEST_ID="test-$(date +%s)"
ADMIN_BEARER="${ADMIN_BEARER:-}" # Optional. When empty, gcloud will mint an ID token.
HEADERS=()

if ! command -v jq >/dev/null; then
  echo 'jq is required for validation' >&2
  exit 1
fi

if ! command -v curl >/dev/null; then
  echo 'curl is required for validation' >&2
  exit 1
fi

if [[ -z "$SERVICE_URL" ]]; then
  echo "SERVICE_URL must be provided" >&2
  exit 1
fi

if [[ -z "$TENANT_ID" ]]; then
  echo "TENANT_ID must be provided" >&2
  exit 1
fi

if [[ -z "$ADMIN_BEARER" ]]; then
  ADMIN_BEARER=$(gcloud auth print-identity-token)
fi

HEADERS+=("Authorization: Bearer ${ADMIN_BEARER}")
HEADERS+=("X-Tenant-ID: ${TENANT_ID}")
HEADERS+=("X-Request-ID: ${REQUEST_ID}")

header_args=()
for header in "${HEADERS[@]}"; do
  header_args+=("-H" "$header")
done

echo "Checking /health"
curl -fsS "${SERVICE_URL}/health" >/dev/null

echo "Triggering postings refresh"
POSTINGS_BODY=$(jq -n --arg tid "$TENANT_ID" '{tenantId: $tid, force: false}')
POSTINGS_RESPONSE=$(curl -fsS -X POST "${header_args[@]}" \
  -H "Content-Type: application/json" \
  -d "${POSTINGS_BODY}" \
  "${SERVICE_URL}/v1/admin/refresh-postings")

echo "Response: ${POSTINGS_RESPONSE}"

echo "Triggering profiles refresh"
PROFILES_BODY=$(jq -n --arg tid "$TENANT_ID" '{tenantId: $tid, priority: "low", sinceIso: "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"}')
PROFILES_RESPONSE=$(curl -fsS -X POST "${header_args[@]}" \
  -H "Content-Type: application/json" \
  -d "${PROFILES_BODY}" \
  "${SERVICE_URL}/v1/admin/refresh-profiles")

echo "Response: ${PROFILES_RESPONSE}"

echo "Fetching snapshots"
SNAPSHOT_RESPONSE=$(curl -fsS "${header_args[@]}" "${SERVICE_URL}/v1/admin/snapshots?tenantId=${TENANT_ID}")

echo "Snapshots: ${SNAPSHOT_RESPONSE}"

echo "Validation completed"
