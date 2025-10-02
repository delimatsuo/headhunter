#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

PROJECT_ID="${PROJECT_ID:-headhunter-ai-0088}"
COLLECTION="${COLLECTION:-organizations}"
REGION="${REGION:-us-central1}"
IDP_DOMAIN="${IDP_DOMAIN:-}"
IDP_MGMT_CLIENT_ID="${IDP_MGMT_CLIENT_ID:-}"
IDP_MGMT_CLIENT_SECRET="${IDP_MGMT_CLIENT_SECRET:-}"
IDP_DEFAULT_AUDIENCE="${IDP_DEFAULT_AUDIENCE:-https://api.ella.jobs/gateway}"
IDP_ALLOWED_SCOPES="${IDP_ALLOWED_SCOPES:-}"  # Comma-separated list
LOG_NAMESPACE="oauth"
SECRET_REGION_OVERRIDE="${REGION:-us-central1}"
ROTATION_DAYS=30
COMMAND=""

usage() {
  cat <<USAGE
Usage: PROJECT_ID=... IDP_DOMAIN=... IDP_MGMT_CLIENT_ID=... IDP_MGMT_CLIENT_SECRET=... \
       scripts/configure_oauth2_clients.sh [options] [provision|rotate|revoke]

Environment variables:
  PROJECT_ID                GCP project containing the Firestore tenant collection and Secret Manager.
  COLLECTION                Firestore collection for tenants (default: organizations).
  REGION                    Location used when creating secrets (default: us-central1).
  IDP_DOMAIN                Base domain for the IdP (e.g. idp.ella.jobs).
  IDP_MGMT_CLIENT_ID        Management API client ID used to administer the IdP.
  IDP_MGMT_CLIENT_SECRET    Management API client secret.
  IDP_DEFAULT_AUDIENCE      Audience/API identifier assigned to client grants.
  IDP_ALLOWED_SCOPES        Comma-separated scopes to assign to the client grant (optional).

Options:
  --secret-region REGION    Location to use for Secret Manager replication (default: ${REGION}).
  --rotation-days DAYS      Rotation cadence in days for oauth-client-* secrets (default: 30).
  -h, --help                Show this message.

Commands:
  provision (default)       Create OAuth clients for all active tenants.
  rotate                    Rotate client credentials.
  revoke                    Revoke client credentials.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    provision|create)
      COMMAND="provision"
      shift
      ;;
    rotate)
      COMMAND="rotate"
      shift
      ;;
    revoke|delete)
      COMMAND="revoke"
      shift
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
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$COMMAND" ]]; then
  COMMAND="provision"
fi

if ! [[ "$ROTATION_DAYS" =~ ^[0-9]+$ ]]; then
  echo "--rotation-days must be an integer" >&2
  exit 1
fi

ROTATION_PERIOD_SECONDS=$((ROTATION_DAYS * 86400))

if [[ -z "$PROJECT_ID" || -z "$IDP_DOMAIN" || -z "$IDP_MGMT_CLIENT_ID" || -z "$IDP_MGMT_CLIENT_SECRET" ]]; then
  usage >&2
  exit 1
fi

log() {
  printf '[%s][%s] %s\n' "$LOG_NAMESPACE" "$PROJECT_ID" "$*"
}

warn() {
  log "WARN: $*"
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

fail() {
  log "ERROR: $*"
  exit 1
}

normalize_domain() {
  local domain="$1"
  domain="${domain#https://}"
  domain="${domain#http://}"
  echo "${domain%%/}"
}

IDP_HOST="$(normalize_domain "$IDP_DOMAIN")"
MGMT_AUDIENCE="https://${IDP_HOST}/api/v2/"
IDP_BASE_URL="https://${IDP_HOST}"

SCOPES_JSON='[]'
if [[ -n "$IDP_ALLOWED_SCOPES" ]]; then
  SCOPES_JSON=$(jq -n --arg scopes "$IDP_ALLOWED_SCOPES" '$scopes | split(",") | map(. | gsub("^\\s+|\\s+$"; "")) | map(select(length > 0))')
fi

gcloud config set project "$PROJECT_ID" >/dev/null

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command '$1' not found" >&2
    exit 1
  fi
}

require_command jq
require_command python3
require_command curl

log "Using project ${PROJECT_ID}"

retry_curl() {
  curl --retry 4 --retry-delay 2 --retry-connrefused --fail --silent --show-error "$@"
}

obtain_management_token() {
  retry_curl "${IDP_BASE_URL}/oauth/token" \
    -H 'Content-Type: application/json' \
    -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"${IDP_MGMT_CLIENT_ID}\",\"client_secret\":\"${IDP_MGMT_CLIENT_SECRET}\",\"audience\":\"${MGMT_AUDIENCE}\"}" \
    | jq -r '.access_token'
}

MGMT_TOKEN="$(obtain_management_token)"
if [[ -z "$MGMT_TOKEN" || "$MGMT_TOKEN" == "null" ]]; then
  fail "Failed to obtain IdP management token"
fi

idp_get() {
  local path="$1"
  retry_curl "${IDP_BASE_URL}/api/v2${path}" -H "Authorization: Bearer ${MGMT_TOKEN}"
}

idp_post() {
  local path="$1"
  local payload="$2"
  retry_curl -X POST "${IDP_BASE_URL}/api/v2${path}" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${MGMT_TOKEN}" \
    -d "$payload"
}

idp_delete() {
  local path="$1"
  retry_curl -X DELETE "${IDP_BASE_URL}/api/v2${path}" \
    -H "Authorization: Bearer ${MGMT_TOKEN}"
}

fetch_tenants() {
  python3 <<'PY'
import json
import os
import sys

from google.api_core.exceptions import NotFound, PermissionDenied
from google.cloud import firestore

project_id = os.environ.get('PROJECT_ID')
collection = os.environ.get('COLLECTION', 'organizations')

client = firestore.Client(project=project_id)
try:
    query = client.collection(collection).where('status', '==', 'active')
    rendered = False
    for doc in query.stream():
        data = doc.to_dict()
        data['id'] = doc.id
        print(json.dumps(data))
        rendered = True
    if not rendered:
        print(json.dumps({'__empty__': True}))
except (NotFound, PermissionDenied) as exc:
    sys.stderr.write(f"Firestore collection validation failed: {exc}\n")
    sys.exit(3)
except Exception as exc:  # pylint: disable=broad-except
    sys.stderr.write(f"Unexpected Firestore error: {exc}\n")
    sys.exit(4)
PY
}

validate_firestore_access() {
  local result
  if ! result=$(fetch_tenants); then
    fail "Unable to access Firestore collection ${COLLECTION}"
  fi

  if grep -q '"__empty__"' <<<"${result}"; then
    log "No active tenants found in ${COLLECTION}; continuing"
    echo "${result}"
  else
    echo "${result}"
  fi
}

ensure_secret_exists() {
  local secret_name="$1"
  local describe_output
  if ! describe_output=$(gcloud secrets describe "$secret_name" --format='value(replication.policy)' 2>/dev/null); then
    gcloud secrets create "$secret_name" \
      --replication-policy="user-managed" \
      --locations="${SECRET_REGION_OVERRIDE}" >/dev/null
  else
    if [[ "$describe_output" != "user-managed" ]]; then
      warn "Secret ${secret_name} uses ${describe_output} replication (expected user-managed in ${SECRET_REGION_OVERRIDE})"
    fi
  fi
  apply_rotation_policy "$secret_name"
}

store_credentials() {
  local secret_name="$1"
  local client_id="$2"
  local client_secret="$3"
  local tenant_id="$4"

  ensure_secret_exists "$secret_name"

  jq -n \
    --arg client_id "$client_id" \
    --arg client_secret "$client_secret" \
    --arg tenant_id "$tenant_id" \
    --arg audience "$IDP_DEFAULT_AUDIENCE" \
    '{client_id: $client_id, client_secret: $client_secret, tenant_id: $tenant_id, audience: $audience}' \
    | gcloud secrets versions add "$secret_name" --data-file=- >/dev/null
}

validate_client_credentials() {
  local client_id="$1"
  local client_secret="$2"
  local tenant_id="$3"
  local response
  response=$(retry_curl "${IDP_BASE_URL}/oauth/token" \
    -H 'Content-Type: application/json' \
    -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"${client_id}\",\"client_secret\":\"${client_secret}\",\"audience\":\"${IDP_DEFAULT_AUDIENCE}\"}")

  local access_token
  access_token=$(echo "$response" | jq -r '.access_token // empty')
  if [[ -z "$access_token" ]]; then
    fail "Credential validation failed for tenant ${tenant_id}: ${response}"
  fi
}

create_client() {
  local tenant_id="$1"
  local display_name="$2"
  local payload
  payload=$(jq -n \
    --arg name "${display_name} Gateway Client" \
    --arg desc "Ella gateway client for tenant ${tenant_id}" \
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
  client_id=$(echo "$response" | jq -r '.client_id')
  client_secret=$(echo "$response" | jq -r '.client_secret')

  if [[ -z "$client_id" || -z "$client_secret" ]]; then
    fail "Failed to create client for ${tenant_id}: ${response}"
  fi

  local grant_payload
  grant_payload=$(jq -n \
    --arg client_id "$client_id" \
    --arg audience "$IDP_DEFAULT_AUDIENCE" \
    --argjson scopes "$SCOPES_JSON" \
    '{client_id: $client_id, audience: $audience, scope: $scopes}')

  idp_post "/client-grants" "$grant_payload" >/dev/null

  local secret_name="oauth-client-${tenant_id}"
  store_credentials "$secret_name" "$client_id" "$client_secret" "$tenant_id"
  validate_client_credentials "$client_id" "$client_secret" "$tenant_id"
  log "Provisioned client ${client_id} for tenant ${tenant_id}"
}

rotate_client() {
  local tenant_id="$1"
  local secret_name="oauth-client-${tenant_id}"
  local existing
  existing=$(gcloud secrets versions access latest --secret="$secret_name" 2>/dev/null || true)
  if [[ -z "$existing" ]]; then
    log "Skipping rotation for ${tenant_id}; secret not found"
    return
  fi

  local client_id
  client_id=$(echo "$existing" | jq -r '.client_id')
  if [[ -z "$client_id" || "$client_id" == "null" ]]; then
    log "Secret for ${tenant_id} does not include client_id"
    return
  fi

  local response
  response=$(idp_post "/clients/${client_id}/rotate-secret" '{}')
  local client_secret
  client_secret=$(echo "$response" | jq -r '.client_secret')
  if [[ -z "$client_secret" || "$client_secret" == "null" ]]; then
    fail "Failed to rotate secret for ${tenant_id}: ${response}"
    return
  fi

  store_credentials "$secret_name" "$client_id" "$client_secret" "$tenant_id"
  validate_client_credentials "$client_id" "$client_secret" "$tenant_id"
  log "Rotated secret for tenant ${tenant_id}"
}

revoke_client() {
  local tenant_id="$1"
  local secret_name="oauth-client-${tenant_id}"
  local existing
  existing=$(gcloud secrets versions access latest --secret="$secret_name" 2>/dev/null || true)
  if [[ -z "$existing" ]]; then
    log "No secret for ${tenant_id}; nothing to revoke"
    return
  fi

  local client_id
  client_id=$(echo "$existing" | jq -r '.client_id')
  if [[ -z "$client_id" || "$client_id" == "null" ]]; then
    log "Secret for ${tenant_id} missing client_id"
    return
  fi

  idp_delete "/clients/${client_id}" >/dev/null || true

  jq -n \
    --arg client_id "$client_id" \
    --arg tenant_id "$tenant_id" \
    --arg revoked_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    '{client_id: $client_id, tenant_id: $tenant_id, revoked_at: $revoked_at}' \
    | gcloud secrets versions add "$secret_name" --data-file=- >/dev/null

  log "Revoked client ${client_id} for tenant ${tenant_id}"
}

process_tenants() {
  local action="$1"
  local json_line tenant_id display_name
  local tenants_json
  tenants_json=$(validate_firestore_access)

  if grep -q '__empty__' <<<"${tenants_json}"; then
    log "No active tenants to process"
    return
  fi

  while IFS= read -r json_line; do
    [[ -z "$json_line" ]] && continue
    tenant_id=$(echo "$json_line" | jq -r '.id')
    if [[ -z "$tenant_id" || "$tenant_id" == "null" ]]; then
      log "Skipping malformed tenant payload: ${json_line}"
      continue
    fi
    display_name=$(echo "$json_line" | jq -r '.name // ("tenant-" + .id)')

    case "$action" in
      provision)
        local secret_name="oauth-client-${tenant_id}"
        if gcloud secrets describe "$secret_name" >/dev/null 2>&1; then
          log "Secret ${secret_name} already exists; skipping"
          continue
        fi
        create_client "$tenant_id" "$display_name"
        ;;
      rotate)
        rotate_client "$tenant_id"
        ;;
      revoke)
        revoke_client "$tenant_id"
        ;;
      *)
        fail "Unknown action ${action}"
        ;;
    esac
  done <<<"${tenants_json}"
}

case "$COMMAND" in
  provision|create)
    process_tenants provision
    ;;
  rotate)
    process_tenants rotate
    ;;
  revoke|delete)
    process_tenants revoke
    ;;
  *)
    usage >&2
    fail "Unsupported command ${COMMAND}"
    ;;
 esac

log "OAuth2 client automation complete"
