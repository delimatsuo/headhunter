#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

COMMAND="${1:-help}"
shift || true

PROJECT_ID="${PROJECT_ID:-}"
COLLECTION="organizations"
IDP_DOMAIN=""
IDP_MGMT_CLIENT_ID=""
IDP_MGMT_CLIENT_SECRET=""
IDP_DEFAULT_AUDIENCE="https://api.ella.jobs/gateway"
IDP_ALLOWED_SCOPES=""
TENANT_ID=""
OUTPUT_PATH=""
OUTPUT_FORMAT="table"
SECRET_REGION_OVERRIDE="${REGION:-us-central1}"
ROTATION_DAYS=30

usage() {
  cat <<USAGE
Usage: $(basename "$0") <command> [options]

Commands:
  list                          List tenant OAuth2 credential status.
  provision --tenant TENANT_ID  Provision credentials for a tenant.
  rotate --tenant TENANT_ID     Rotate credentials for a tenant.
  revoke --tenant TENANT_ID     Revoke credentials for a tenant.
  test --tenant TENANT_ID       Test OAuth2 client credentials for a tenant.
  report [--output PATH]        Generate credential status report.

Common options:
  --project-id ID               GCP project containing Firestore and Secret Manager.
  --collection NAME             Firestore collection for tenants (default: organizations).
  --idp-domain DOMAIN           Identity provider base domain (e.g. idp.ella.jobs).
  --idp-client-id ID            IdP management API client ID.
  --idp-client-secret SECRET    IdP management API client secret.
  --audience AUDIENCE           OAuth audience override (default: https://api.ella.jobs/gateway).
  --scopes SCOPES               Comma-separated scopes for client grants.
  --tenant TENANT_ID            Target tenant id for single-tenant commands.
  --output PATH                 Output path for reports.
  --format table|json|markdown  Report format (default: table).
  --secret-region REGION        Secret Manager replication region (default: ${REGION:-us-central1}).
  --rotation-days DAYS          Rotation cadence in days for oauth-client-* secrets (default: 30).
  -h, --help                    Show this help message.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      PROJECT_ID="$2"
      shift 2
      ;;
    --collection)
      COLLECTION="$2"
      shift 2
      ;;
    --idp-domain)
      IDP_DOMAIN="$2"
      shift 2
      ;;
    --idp-client-id)
      IDP_MGMT_CLIENT_ID="$2"
      shift 2
      ;;
    --idp-client-secret)
      IDP_MGMT_CLIENT_SECRET="$2"
      shift 2
      ;;
    --audience)
      IDP_DEFAULT_AUDIENCE="$2"
      shift 2
      ;;
    --scopes)
      IDP_ALLOWED_SCOPES="$2"
      shift 2
      ;;
    --tenant)
      TENANT_ID="$2"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="$2"
      shift 2
      ;;
    --format)
      OUTPUT_FORMAT="$2"
      shift 2
      ;;
    --secret-region)
      SECRET_REGION_OVERRIDE="$2"
      shift 2
      ;;
    --rotation-days)
      ROTATION_DAYS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command '$1' not found" >&2
    exit 2
  fi
}

log() {
  printf '[tenant-credentials][%s] %s\n' "$(date -Is)" "$*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

warn() {
  log "WARN: $*"
}

normalize_domain() {
  local domain="$1"
  domain="${domain#https://}"
  domain="${domain#http://}"
  echo "${domain%%/}"
}

require_command gcloud
require_command jq
require_command python3

if [[ -z "$PROJECT_ID" ]]; then
  fail "--project-id is required"
fi

if ! [[ "$ROTATION_DAYS" =~ ^[0-9]+$ ]]; then
  fail "--rotation-days must be an integer"
fi

ROTATION_PERIOD_SECONDS=$((ROTATION_DAYS * 86400))

gcloud config set project "$PROJECT_ID" >/dev/null 2>&1 || true

MGMT_TOKEN=""
IDP_HOST=""
SCOPES_JSON='[]'

init_idp() {
  if [[ -z "$IDP_DOMAIN" || -z "$IDP_MGMT_CLIENT_ID" || -z "$IDP_MGMT_CLIENT_SECRET" ]]; then
    fail "IdP domain, client id, and client secret are required for this command"
  fi
  require_command curl
  IDP_HOST="$(normalize_domain "$IDP_DOMAIN")"
  local mgmt_audience="https://${IDP_HOST}/api/v2/"
  SCOPES_JSON='[]'
  if [[ -n "$IDP_ALLOWED_SCOPES" ]]; then
    SCOPES_JSON=$(jq -n --arg scopes "$IDP_ALLOWED_SCOPES" '$scopes | split(",") | map(. | gsub("^\\s+|\\s+$"; "")) | map(select(length>0))')
  fi
  MGMT_TOKEN=$(curl --retry 4 --retry-connrefused --retry-delay 2 --fail --silent --show-error "https://${IDP_HOST}/oauth/token" \
    -H 'Content-Type: application/json' \
    -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"${IDP_MGMT_CLIENT_ID}\",\"client_secret\":\"${IDP_MGMT_CLIENT_SECRET}\",\"audience\":\"${mgmt_audience}\"}")
  MGMT_TOKEN=$(jq -r '.access_token // empty' <<<"$MGMT_TOKEN")
  if [[ -z "$MGMT_TOKEN" ]]; then
    fail "Failed to obtain IdP management token"
  fi
}

idp_post() {
  local path="$1"
  local payload="$2"
  curl --retry 4 --retry-delay 2 --retry-connrefused --fail --silent --show-error \
    -X POST "https://${IDP_HOST}/api/v2${path}" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${MGMT_TOKEN}" \
    -d "$payload"
}

idp_delete() {
  local path="$1"
  curl --retry 4 --retry-delay 2 --retry-connrefused --fail --silent --show-error \
    -X DELETE "https://${IDP_HOST}/api/v2${path}" \
    -H "Authorization: Bearer ${MGMT_TOKEN}"
}

fetch_tenants() {
  python3 <<'PY'
import json
import os
import sys
from google.api_core.exceptions import PermissionDenied, NotFound
from google.cloud import firestore

project_id = os.environ['PROJECT_ID']
collection = os.environ.get('COLLECTION', 'organizations')
target = os.environ.get('TARGET_TENANT')

def emit(doc, data):
    payload = {
        'id': doc.id,
        'name': data.get('name', doc.id),
        'status': data.get('status', 'unknown')
    }
    print(json.dumps(payload))

client = firestore.Client(project=project_id)
try:
    if target:
        doc = client.collection(collection).document(target).get()
        if doc.exists:
            emit(doc, doc.to_dict())
    else:
        query = client.collection(collection).where('status', 'in', ['active', 'pending'])
        for doc in query.stream():
            emit(doc, doc.to_dict())
except (PermissionDenied, NotFound) as exc:
    sys.stderr.write(f"Firestore error: {exc}\n")
    sys.exit(3)
except Exception as exc:  # pylint: disable=broad-except
    sys.stderr.write(f"Unexpected Firestore error: {exc}\n")
    sys.exit(4)
PY
}

ensure_secret() {
  local secret_name="$1"
  local replication
  if ! replication=$(gcloud secrets describe "$secret_name" --format='value(replication.policy)' 2>/dev/null); then
    gcloud secrets create "$secret_name" \
      --replication-policy="user-managed" \
      --locations="${SECRET_REGION_OVERRIDE}" >/dev/null
  elif [[ "$replication" != "user-managed" ]]; then
    warn "Secret ${secret_name} uses ${replication} replication (expected user-managed in ${SECRET_REGION_OVERRIDE})"
  fi
}

next_rotation_timestamp() {
  local days="$1"
  local ts
  if ts=$(date -u -v+"${days}"d '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null); then
    printf '%s' "$ts"
    return
  fi
  if ts=$(date -u -d "+${days} days" '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null); then
    printf '%s' "$ts"
    return
  fi
  date -u '+%Y-%m-%dT%H:%M:%SZ'
}

apply_rotation_policy() {
  local secret_name="$1"
  local period="${ROTATION_PERIOD_SECONDS}s"
  local next_time
  next_time=$(next_rotation_timestamp "$ROTATION_DAYS")
  gcloud secrets update "$secret_name" \
    --project="$PROJECT_ID" \
    --rotation-period="$period" \
    --next-rotation-time="$next_time" >/dev/null 2>&1 || true
}

store_credentials() {
  local secret_name="$1"
  local client_id="$2"
  local client_secret="$3"
  local tenant_id="$4"
  ensure_secret "$secret_name"
  apply_rotation_policy "$secret_name"
  jq -n \
    --arg client_id "$client_id" \
    --arg client_secret "$client_secret" \
    --arg tenant_id "$tenant_id" \
    --arg audience "$IDP_DEFAULT_AUDIENCE" \
    '{client_id:$client_id, client_secret:$client_secret, tenant_id:$tenant_id, audience:$audience}' \
    | gcloud secrets versions add "$secret_name" --data-file=- >/dev/null
}

create_client() {
  local tenant_id="$1"
  local display_name="$2"
  init_idp
  local payload
  payload=$(jq -n \
    --arg name "${display_name} Gateway Client" \
    --arg desc "OAuth client for tenant ${tenant_id}" \
    --arg tenant "$tenant_id" \
    '{
      name: $name,
      description: $desc,
      app_type: "non_interactive",
      token_endpoint_auth_method: "client_secret_post",
      grant_types: ["client_credentials"],
      client_metadata: { tenant_id: $tenant },
      jwt_configuration: { alg: "RS256", lifetime_in_seconds: 3600 }
    }')
  local response
  response=$(idp_post "/clients" "$payload")
  local client_id client_secret
  client_id=$(echo "$response" | jq -r '.client_id // empty')
  client_secret=$(echo "$response" | jq -r '.client_secret // empty')
  if [[ -z "$client_id" || -z "$client_secret" ]]; then
    fail "Failed to create client for ${tenant_id}: ${response}"
  fi

  local grant_payload
  grant_payload=$(jq -n \
    --arg client_id "$client_id" \
    --arg audience "$IDP_DEFAULT_AUDIENCE" \
    --argjson scopes "$SCOPES_JSON" \
    '{client_id:$client_id, audience:$audience, scope:$scopes}')
  idp_post "/client-grants" "$grant_payload" >/dev/null

  local secret_name="oauth-client-${tenant_id}"
  store_credentials "$secret_name" "$client_id" "$client_secret" "$tenant_id"
  log "Provisioned credentials for ${tenant_id}"
}

rotate_client() {
  local tenant_id="$1"
  init_idp
  local secret_name="oauth-client-${tenant_id}"
  local payload
  payload=$(gcloud secrets versions access latest --secret="$secret_name" 2>/dev/null || true)
  if [[ -z "$payload" ]]; then
    fail "Secret ${secret_name} not found"
  fi
  local client_id
  client_id=$(jq -r '.client_id // empty' <<<"$payload")
  if [[ -z "$client_id" ]]; then
    fail "Secret for ${tenant_id} missing client_id"
  fi
  local response
  response=$(idp_post "/clients/${client_id}/rotate-secret" '{}')
  local client_secret
  client_secret=$(echo "$response" | jq -r '.client_secret // empty')
  if [[ -z "$client_secret" ]]; then
    fail "Failed to rotate secret for ${tenant_id}: ${response}"
  fi
  store_credentials "$secret_name" "$client_id" "$client_secret" "$tenant_id"
  log "Rotated credentials for ${tenant_id}"
}

revoke_client() {
  local tenant_id="$1"
  init_idp
  local secret_name="oauth-client-${tenant_id}"
  local payload
  payload=$(gcloud secrets versions access latest --secret="$secret_name" 2>/dev/null || true)
  if [[ -z "$payload" ]]; then
    fail "Secret ${secret_name} not found"
  fi
  local client_id
  client_id=$(jq -r '.client_id // empty' <<<"$payload")
  if [[ -z "$client_id" ]]; then
    fail "Secret for ${tenant_id} missing client_id"
  fi
  idp_delete "/clients/${client_id}" >/dev/null || true
  store_credentials "$secret_name" "$client_id" "REVOKED" "$tenant_id"
  log "Revoked credentials for ${tenant_id}"
}

fetch_secret_status() {
  local tenant_id="$1"
  local secret_name="oauth-client-${tenant_id}"
  if ! gcloud secrets describe "$secret_name" >/dev/null 2>&1; then
    echo "missing"
    return
  fi
  local latest
  latest=$(gcloud secrets versions list "$secret_name" --sort-by='createTime' --limit=1 --format='value(createTime)' 2>/dev/null || true)
  echo "${latest:-unknown}"
}

test_credentials() {
  local tenant_id="$1"
  require_command curl
  local secret_name="oauth-client-${tenant_id}"
  local payload
  payload=$(gcloud secrets versions access latest --secret="$secret_name" 2>/dev/null || true)
  if [[ -z "$payload" ]]; then
    fail "Secret ${secret_name} not found"
  fi
  local client_id client_secret audience
  client_id=$(jq -r '.client_id // empty' <<<"$payload")
  client_secret=$(jq -r '.client_secret // empty' <<<"$payload")
  audience=$(jq -r '.audience // empty' <<<"$payload")
  if [[ -z "$client_id" || -z "$client_secret" ]]; then
    fail "Secret payload incomplete for ${tenant_id}"
  fi
  if [[ "$client_secret" == "REVOKED" ]]; then
    fail "Credentials for ${tenant_id} are revoked"
  fi
  if [[ -z "$IDP_DOMAIN" ]]; then
    fail "--idp-domain is required for credential testing"
  fi
  local domain
  domain="$(normalize_domain "$IDP_DOMAIN")"
  local request
  request=$(jq -n \
    --arg client_id "$client_id" \
    --arg client_secret "$client_secret" \
    --arg audience "${IDP_DEFAULT_AUDIENCE:-$audience}" \
    --arg scopes "$IDP_ALLOWED_SCOPES" \
    '{grant_type:"client_credentials", client_id:$client_id, client_secret:$client_secret, audience:$audience, scope:($scopes | select(length>0))}')
  local response
  response=$(curl --fail --silent --show-error "https://${domain}/oauth/token" -H 'Content-Type: application/json' -d "$request" 2>/dev/null)
  local token
  token=$(jq -r '.access_token // empty' <<<"$response")
  if [[ -z "$token" ]]; then
    fail "Token request failed for ${tenant_id}: ${response}"
  fi
  log "Obtained access token for ${tenant_id}"
}

list_tenants() {
  local json_lines
  if ! json_lines=$(PROJECT_ID="$PROJECT_ID" COLLECTION="$COLLECTION" fetch_tenants 2>/dev/null); then
    fail "Unable to fetch tenants"
  fi
  if [[ -z "$json_lines" ]]; then
    log "No tenants found"
    return
  fi
  if [[ "$OUTPUT_FORMAT" == "json" ]]; then
    local enriched
    enriched=$(while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      local tenant
      tenant=$(echo "$line" | jq -r '.id')
      local secret_time
      secret_time=$(fetch_secret_status "$tenant")
      jq --arg secret "$secret_time" '. + {secret_status:$secret}' <<<"$line"
    done <<<"$json_lines" | jq -s '.')
    printf '%s\n' "$enriched"
    return
  fi
  printf '%-36s %-24s %-12s %-25s\n' "TENANT" "NAME" "STATUS" "SECRET_UPDATED"
  printf '%s\n' "$(printf '%.0s-' {1..110})"
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    local tenant name status secret_time
    tenant=$(echo "$line" | jq -r '.id')
    name=$(echo "$line" | jq -r '.name')
    status=$(echo "$line" | jq -r '.status')
    secret_time=$(fetch_secret_status "$tenant")
    printf '%-36s %-24s %-12s %-25s\n' "$tenant" "$name" "$status" "$secret_time"
  done <<<"$json_lines"
}

report_tenants() {
  local json_lines
  if ! json_lines=$(PROJECT_ID="$PROJECT_ID" COLLECTION="$COLLECTION" fetch_tenants 2>/dev/null); then
    fail "Unable to fetch tenants"
  fi
  local timestamp
  timestamp="$(date -u '+%Y-%m-%d %H:%M:%SZ')"
  local dest="$OUTPUT_PATH"
  if [[ -z "$dest" ]]; then
    local ext="md"
    case "$OUTPUT_FORMAT" in
      json) ext="json" ;;
      markdown) ext="md" ;;
      table|text) ext="txt" ;;
    esac
    dest="reports/tenant_credentials_${timestamp//[: ]/_}.${ext}"
  fi
  mkdir -p "$(dirname "$dest")"
  case "$OUTPUT_FORMAT" in
    json)
      local enriched
      enriched=$(while IFS= read -r line; do
        tenant=$(echo "$line" | jq -r '.id')
        secret_time=$(fetch_secret_status "$tenant")
        jq --arg secret "$secret_time" '. + {secret_status: $secret}' <<<"$line"
      done <<<"$json_lines" | jq -s '.')
      printf '%s\n' "$enriched" | tee "$dest" >/dev/null
      ;;
    markdown)
      {
        printf '# Tenant Credential Report\n\n'
        printf '- Project: %s\n' "$PROJECT_ID"
        printf '- Generated: %s\n\n' "$timestamp"
        printf '| Tenant | Name | Status | Secret Updated |\n'
        printf '|--------|------|--------|----------------|\n'
        while IFS= read -r line; do
          tenant=$(echo "$line" | jq -r '.id')
          name=$(echo "$line" | jq -r '.name')
          status=$(echo "$line" | jq -r '.status')
          updated=$(fetch_secret_status "$tenant")
          printf '| %s | %s | %s | %s |\n' "$tenant" "$name" "$status" "$updated"
        done <<<"$json_lines"
      } | tee "$dest" >/dev/null
      ;;
    *)
      OUTPUT_FORMAT="table"
      list_tenants | tee "$dest" >/dev/null
      ;;
  esac
  log "Credential report written to ${dest}"
}

case "$COMMAND" in
  list)
    list_tenants
    ;;
  provision)
    if [[ -z "$TENANT_ID" ]]; then
      fail "--tenant is required for provisioning"
    fi
    tenant_payload=$(PROJECT_ID="$PROJECT_ID" COLLECTION="$COLLECTION" TARGET_TENANT="$TENANT_ID" fetch_tenants)
    if [[ -z "$tenant_payload" ]]; then
      fail "Tenant ${TENANT_ID} not found"
    fi
    display_name=$(echo "$tenant_payload" | head -n1 | jq -r '.name // ("tenant-" + .id)')
    create_client "$TENANT_ID" "$display_name"
    ;;
  rotate)
    if [[ -z "$TENANT_ID" ]]; then
      fail "--tenant is required for rotation"
    fi
    rotate_client "$TENANT_ID"
    ;;
  revoke)
    if [[ -z "$TENANT_ID" ]]; then
      fail "--tenant is required for revocation"
    fi
    revoke_client "$TENANT_ID"
    ;;
  test)
    if [[ -z "$TENANT_ID" ]]; then
      fail "--tenant is required for testing"
    fi
    test_credentials "$TENANT_ID"
    ;;
  report)
    report_tenants
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    echo "Unknown command: ${COMMAND}" >&2
    usage
    exit 1
    ;;
esac
