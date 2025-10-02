#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Validate API Gateway deployment end-to-end.

GATEWAY_HOST="${GATEWAY_HOST:-}"
TENANT_ID="${TENANT_ID:-}"
CLIENT_ID="${CLIENT_ID:-}"
CLIENT_SECRET="${CLIENT_SECRET:-}"
AUDIENCE_OVERRIDE="${AUDIENCE:-}"
TOKEN_ENDPOINT="${TOKEN_ENDPOINT:-https://idp.ella.jobs/oauth/token}"

if [[ -z "$GATEWAY_HOST" || -z "$TENANT_ID" || -z "$CLIENT_ID" || -z "$CLIENT_SECRET" ]]; then
  echo "GATEWAY_HOST, TENANT_ID, CLIENT_ID, and CLIENT_SECRET must be provided" >&2
  exit 1
fi

audience="${AUDIENCE_OVERRIDE:-${GATEWAY_AUDIENCE:-https://api.ella.jobs/gateway}}"

token_response=$(curl -fsS "$TOKEN_ENDPOINT" \
  -H 'Content-Type: application/json' \
  -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"${CLIENT_ID}\",\"client_secret\":\"${CLIENT_SECRET}\",\"audience\":\"${audience}\"}")

token=$(echo "$token_response" | jq -r '.access_token')
if [[ -z "$token" || "$token" == "null" ]]; then
  echo "Failed to obtain access token" >&2
  echo "$token_response" >&2
  exit 1
fi

echo "Token acquired"

invoke() {
  local method="$1"
  local path="$2"
  local payload="$3"
  echo "Testing ${method} ${path}"
  curl -fsS "https://${GATEWAY_HOST}${path}" \
    -X "$method" \
    -H "Authorization: Bearer ${token}" \
    -H "X-Tenant-ID: ${TENANT_ID}" \
    -H "Content-Type: application/json" \
    ${payload:+-d "$payload"} >/dev/null
}

invoke POST /v1/embeddings/generate '{"items":[{"id":"demo","text":"hello"}]}'
invoke POST /v1/search/hybrid '{"query":"gcp engineer"}'
invoke POST /v1/search/rerank '{"query":"gcp engineer","documents":[]}'
invoke GET /v1/evidence/summaries ''
invoke GET /v1/occupations/demo-role ''
invoke GET '/v1/skills/autocomplete?q=python' ''
invoke POST /v1/market/insights '{"role":"data scientist","location":"SF"}'
invoke POST /v1/roles/match '{"roleId":"role-1","candidates":[]}'
invoke GET /v1/admin/tenants ''

echo "Functional checks passed"

if command -v k6 >/dev/null; then
  echo "Running k6 load test"
  k6 run --vus 30 --duration 1m - <<K6
import http from 'k6/http';
import { check } from 'k6';

const token = '${token}';
const host = 'https://${GATEWAY_HOST}';
const tenant = '${TENANT_ID}';

export default function () {
  const res = http.post(
    `${host}/v1/search/hybrid`,
    JSON.stringify({ query: 'software engineer', limit: 5 }),
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Tenant-ID': tenant,
        'Content-Type': 'application/json'
      }
    }
  );

  check(res, {
    'status is 200': (r) => r.status === 200,
    'p95 latency under 250ms': (r) => r.timings.duration < 250
  });
}
K6
else
  echo "k6 not installed; skipping load test"
fi

echo "Gateway validation complete"
