#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

CONFIG_PATH="config/infrastructure/headhunter-production.env"
PROJECT_ID=""
OUTPUT_PATH=""
FORMAT="markdown"
IDP_DOMAIN=""
IDP_AUDIENCE=""
IDP_SCOPES=""
SKIP_OAUTH_VALIDATION=false
SKIP_TESTS=false
ENVIRONMENT="production"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Options:
  --project-id ID             Target GCP project id
  --config PATH               Infrastructure config (default: ${CONFIG_PATH})
  --output PATH               Write validation report to file
  --format FORMAT             Report format: markdown|text|json (default: markdown)
  --idp-domain DOMAIN         Identity provider domain for OAuth validation
  --idp-audience AUDIENCE     OAuth audience override (defaults to secret value)
  --idp-scopes SCOPES         Comma-separated scopes for validation token requests
  --skip-oauth-validation     Skip OAuth credential validation
  --skip-tests                Skip auth integration test execution
  --environment NAME          Environment suffix (default: production)
  -h, --help                  Show this help message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      PROJECT_ID="$2"
      shift 2
      ;;
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="$2"
      shift 2
      ;;
    --format)
      FORMAT="$2"
      shift 2
      ;;
    --idp-domain)
      IDP_DOMAIN="$2"
      shift 2
      ;;
    --idp-audience)
      IDP_AUDIENCE="$2"
      shift 2
      ;;
    --idp-scopes)
      IDP_SCOPES="$2"
      shift 2
      ;;
    --skip-oauth-validation)
      SKIP_OAUTH_VALIDATION=true
      shift
      ;;
    --skip-tests)
      SKIP_TESTS=true
      shift
      ;;
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config file $CONFIG_PATH not found" >&2
  exit 1
fi

CLI_PROJECT_ID="$PROJECT_ID"

# shellcheck disable=SC1090
source "$CONFIG_PATH"

CONFIG_PROJECT_ID="${PROJECT_ID:-}"
PROJECT_ID="${CLI_PROJECT_ID:-${CONFIG_PROJECT_ID}}"
if [[ -z "$PROJECT_ID" ]]; then
  echo "Project ID must be supplied via --project-id or config" >&2
  exit 1
fi

TENANT_COLLECTION="${COLLECTION:-organizations}"

log() {
  printf '[validate-security][%s] %s\n' "$(date -Is)" "$*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command '$1' not found" >&2
    exit 1
  fi
}

require_command gcloud
require_command jq
require_command python3

SERVICE_ALIASES=(
  "$SVC_EMBED"
  "$SVC_SEARCH"
  "$SVC_RERANK"
  "$SVC_EVIDENCE"
  "$SVC_ECO"
  "$SVC_ENRICH"
  "$SVC_ADMIN"
  "$SVC_MSGS"
)

SECRETS=(
  "$SECRET_DB_PRIMARY"
  "$SECRET_DB_REPLICA"
  "$SECRET_DB_ANALYTICS"
  "$SECRET_TOGETHER_AI"
  "$SECRET_GEMINI_AI"
  "$SECRET_OAUTH_CLIENT"
  "$SECRET_REDIS_ENDPOINT"
  "$SECRET_STORAGE_SIGNER"
)

REGION_DEFAULT="${REGION:-us-central1}"

declare -a VALIDATION_RESULTS=()
OVERALL_STATUS=0

add_result() {
  local name="$1"
  local status="$2"
  local message="$3"
  VALIDATION_RESULTS+=("${name}|${status}|${message}")
  if [[ "$status" == "FAIL" ]]; then
    OVERALL_STATUS=1
  fi
}

service_account_email() {
  echo "$1@${PROJECT_ID}.iam.gserviceaccount.com"
}

CHECK_TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$CHECK_TMP_DIR"' EXIT

gcloud config set project "$PROJECT_ID" >/dev/null 2>&1 || true

REQUIRED_ROLES=()
declare -A REQUIRED_ROLES
REQUIRED_ROLES["$SVC_EMBED"]="roles/cloudsql.client roles/redis.viewer roles/aiplatform.user roles/secretmanager.secretAccessor"
REQUIRED_ROLES["$SVC_SEARCH"]="roles/cloudsql.client roles/redis.viewer roles/secretmanager.secretAccessor"
REQUIRED_ROLES["$SVC_RERANK"]="roles/redis.viewer roles/secretmanager.secretAccessor"
REQUIRED_ROLES["$SVC_EVIDENCE"]="roles/cloudsql.client roles/datastore.viewer roles/redis.viewer roles/secretmanager.secretAccessor"
REQUIRED_ROLES["$SVC_ECO"]="roles/cloudsql.client roles/datastore.viewer roles/redis.viewer roles/secretmanager.secretAccessor"
REQUIRED_ROLES["$SVC_ENRICH"]="roles/cloudsql.client roles/datastore.user roles/pubsub.publisher roles/pubsub.subscriber roles/secretmanager.secretAccessor"
REQUIRED_ROLES["$SVC_ADMIN"]="roles/cloudsql.client roles/pubsub.publisher roles/pubsub.subscriber roles/monitoring.viewer roles/logging.logWriter roles/secretmanager.secretAccessor"
REQUIRED_ROLES["$SVC_MSGS"]="roles/cloudsql.client roles/redis.viewer roles/secretmanager.secretAccessor"

declare -A SECRET_BINDINGS
SECRET_BINDINGS["$SECRET_DB_PRIMARY"]="$SVC_ADMIN $SVC_ENRICH $SVC_MSGS"
SECRET_BINDINGS["$SECRET_DB_REPLICA"]="$SVC_SEARCH $SVC_EVIDENCE $SVC_ECO"
SECRET_BINDINGS["$SECRET_DB_ANALYTICS"]="$SVC_ADMIN $SVC_ENRICH"
SECRET_BINDINGS["$SECRET_TOGETHER_AI"]="$SVC_EMBED $SVC_SEARCH $SVC_RERANK"
SECRET_BINDINGS["$SECRET_GEMINI_AI"]="$SVC_EMBED $SVC_SEARCH"
SECRET_BINDINGS["$SECRET_OAUTH_CLIENT"]="$SVC_ADMIN $SVC_ENRICH"
SECRET_BINDINGS["$SECRET_REDIS_ENDPOINT"]="$SVC_EMBED $SVC_SEARCH $SVC_MSGS $SVC_EVIDENCE $SVC_ECO $SVC_ENRICH"
SECRET_BINDINGS["$SECRET_STORAGE_SIGNER"]="$SVC_ADMIN $SVC_ENRICH"

check_service_accounts() {
  local missing=()
  for alias in "${SERVICE_ALIASES[@]}"; do
    [[ -z "$alias" ]] && continue
    local email
    email="$(service_account_email "$alias")"
    if ! gcloud iam service-accounts describe "$email" >/dev/null 2>&1; then
      missing+=("$email")
    fi
  done
  if (( ${#missing[@]} == 0 )); then
    add_result "Service accounts" "PASS" "All service accounts present"
  else
    add_result "Service accounts" "FAIL" "Missing accounts: ${missing[*]}"
  fi
}

check_service_roles() {
  local policy
  if ! policy=$(gcloud projects get-iam-policy "$PROJECT_ID" --format=json 2>/dev/null); then
    add_result "Project IAM policy" "FAIL" "Unable to fetch project IAM policy"
    return
  fi
  local gaps=()
  for alias in "${SERVICE_ALIASES[@]}"; do
    [[ -z "$alias" ]] && continue
    local roles_string="${REQUIRED_ROLES[$alias]:-}"
    [[ -z "$roles_string" ]] && continue
    local email
    email="$(service_account_email "$alias")"
    local member="serviceAccount:${email}"
    local missing_roles=()
    for role in $roles_string; do
      if ! jq -e --arg role "$role" --arg member "$member" \
        '.bindings[] | select(.role == $role) | select(.members[]? == $member)' <<<"$policy" >/dev/null 2>&1; then
        missing_roles+=("$role")
      fi
    done
    if (( ${#missing_roles[@]} > 0 )); then
      gaps+=("${alias}: ${missing_roles[*]}")
    fi
  done
  if (( ${#gaps[@]} == 0 )); then
    add_result "IAM roles" "PASS" "All required project roles assigned"
  else
    add_result "IAM roles" "FAIL" "Missing bindings -> ${gaps[*]}"
  fi
}

check_secrets() {
  local missing=()
  local binding_issues=()
  for secret in "${SECRETS[@]}"; do
    [[ -z "$secret" ]] && continue
    if ! gcloud secrets describe "$secret" >/dev/null 2>&1; then
      missing+=("$secret")
      continue
    fi
    local policy
    if ! policy=$(gcloud secrets get-iam-policy "$secret" --format=json 2>/dev/null); then
      binding_issues+=("${secret}: unable to retrieve policy")
      continue
    fi
    local required_aliases="${SECRET_BINDINGS[$secret]:-}"
    local missing_members=()
    for alias in $required_aliases; do
      local member="serviceAccount:$(service_account_email "$alias")"
      if ! jq -e --arg member "$member" '.bindings[] | select(.role == "roles/secretmanager.secretAccessor") | select(.members[]? == $member)' <<<"$policy" >/dev/null 2>&1; then
        missing_members+=("$alias")
      fi
    done
    if (( ${#missing_members[@]} > 0 )); then
      binding_issues+=("${secret}: ${missing_members[*]}")
    fi
  done
  if (( ${#missing[@]} == 0 )) && (( ${#binding_issues[@]} == 0 )); then
    add_result "Secret Manager" "PASS" "Secrets and bindings validated"
  else
    local details=""
    if (( ${#missing[@]} > 0 )); then
      details="Missing secrets: ${missing[*]}"
    fi
    if (( ${#binding_issues[@]} > 0 )); then
      details+=" Bindings: ${binding_issues[*]}"
    fi
    add_result "Secret Manager" "FAIL" "$details"
  fi
}

fetch_active_tenants() {
  PROJECT_ID="$PROJECT_ID" python3 <<'PY'
import os
import sys
from typing import List

from google.api_core.exceptions import PermissionDenied, NotFound
from google.cloud import firestore

project_id = os.environ.get("PROJECT_ID")
collection = os.environ.get("TENANT_COLLECTION", "organizations")

try:
    client = firestore.Client(project=project_id)
    query = client.collection(collection).where("status", "==", "active")
    results: List[str] = []
    for doc in query.stream():
        data = doc.to_dict()
        name = data.get("name", doc.id)
        results.append(f"{doc.id}\t{name}")
    for line in results:
        print(line)
except (PermissionDenied, NotFound) as exc:
    sys.stderr.write(f"{exc}\n")
    sys.exit(3)
except Exception as exc:  # pylint: disable=broad-except
    sys.stderr.write(f"Unexpected Firestore error: {exc}\n")
    sys.exit(4)
PY
}

validate_oauth_credentials() {
  if [[ "$SKIP_OAUTH_VALIDATION" == "true" ]]; then
    add_result "OAuth credentials" "WARN" "OAuth validation skipped"
    return
  fi
  local tenant_lines
  if ! tenant_lines=$(TENANT_COLLECTION="$TENANT_COLLECTION" fetch_active_tenants 2>"$CHECK_TMP_DIR/firestore.err"); then
    add_result "OAuth credentials" "FAIL" "Unable to query Firestore tenants: $(<"$CHECK_TMP_DIR/firestore.err")"
    return
  fi
  if [[ -z "$tenant_lines" ]]; then
    add_result "OAuth credentials" "WARN" "No active tenants found"
    return
  fi
  require_command gcloud
  local failures=()
  local warns=()
  local tenant
  while IFS=$'\t' read -r tenant name; do
    [[ -z "$tenant" ]] && continue
    local secret_name="oauth-client-${tenant}"
    if ! gcloud secrets describe "$secret_name" >/dev/null 2>&1; then
      failures+=("${tenant}: secret missing")
      continue
    fi
    local secret_payload
    if ! secret_payload=$(gcloud secrets versions access latest --secret="$secret_name" 2>/dev/null); then
      failures+=("${tenant}: unable to read secret payload")
      continue
    fi
    local client_id client_secret audience
    client_id=$(jq -r '.client_id // empty' <<<"$secret_payload")
    client_secret=$(jq -r '.client_secret // empty' <<<"$secret_payload")
    audience=$(jq -r '.audience // empty' <<<"$secret_payload")
    if [[ -z "$client_id" || -z "$client_secret" ]]; then
      failures+=("${tenant}: incomplete secret payload")
      continue
    fi
    if [[ -z "$IDP_DOMAIN" ]]; then
      warns+=("${tenant}: IdP domain not provided; connectivity not tested")
      continue
    fi
    require_command curl
    local token_response
    local data_payload
    local token_audience="${IDP_AUDIENCE:-$audience}"
    data_payload=$(jq -n \
      --arg client_id "$client_id" \
      --arg client_secret "$client_secret" \
      --arg audience "$token_audience" \
      --arg scopes "$IDP_SCOPES" \
      '{grant_type:"client_credentials", client_id:$client_id, client_secret:$client_secret, audience:$audience, scope: ($scopes | select(length > 0))}')
    set +e
    token_response=$(curl --fail --silent --show-error "https://${IDP_DOMAIN}/oauth/token" \
      -H 'Content-Type: application/json' \
      -d "$data_payload" 2>"$CHECK_TMP_DIR/oauth.err")
    local status=$?
    set -e
    if (( status != 0 )); then
      failures+=("${tenant}: token request failed - $(<"$CHECK_TMP_DIR/oauth.err")")
      continue
    fi
    local access_token
    access_token=$(jq -r '.access_token // empty' <<<"$token_response")
    if [[ -z "$access_token" ]]; then
      failures+=("${tenant}: access token missing in response")
    fi
  done <<<"$tenant_lines"

  if (( ${#failures[@]} == 0 )); then
    local message="OAuth secrets validated"
    if (( ${#warns[@]} > 0 )); then
      message+=" ; warnings: ${warns[*]}"
      add_result "OAuth credentials" "WARN" "$message"
    else
      add_result "OAuth credentials" "PASS" "$message"
    fi
  else
    local detail="${failures[*]}"
    if (( ${#warns[@]} > 0 )); then
      detail+=" ; warnings: ${warns[*]}"
    fi
    add_result "OAuth credentials" "FAIL" "$detail"
  fi
}

check_run_invocations() {
  local region="$REGION_DEFAULT"
  local gateway_email="gateway-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"
  local search_email="$(service_account_email "$SVC_SEARCH")"
  local enrich_email="$(service_account_email "$SVC_ENRICH")"
  declare -A EXPECTED
  EXPECTED["${RUN_SERVICE_EMBED:-}"]="${gateway_email} ${search_email} ${enrich_email}"
  EXPECTED["${RUN_SERVICE_RERANK:-}"]="${gateway_email} ${search_email} ${enrich_email}"
  EXPECTED["${RUN_SERVICE_SEARCH:-}"]="${gateway_email} ${enrich_email}"

  local issues=()
  for service in "${!EXPECTED[@]}"; do
    [[ -z "$service" ]] && continue
    local members="${EXPECTED[$service]}"
    local run_service="${service}-${ENVIRONMENT}"
    local policy
    if ! policy=$(gcloud run services get-iam-policy "$run_service" --project "$PROJECT_ID" --region "$region" --format=json 2>/dev/null); then
      issues+=("${run_service}: unable to load IAM policy")
      continue
    fi
    local missing_members=()
    for email in $members; do
      local member="serviceAccount:${email}"
      if ! jq -e --arg member "$member" '.bindings[] | select(.role == "roles/run.invoker") | select(.members[]? == $member)' <<<"$policy" >/dev/null 2>&1; then
        missing_members+=("$member")
      fi
    done
    if (( ${#missing_members[@]} > 0 )); then
      issues+=("${run_service}: ${missing_members[*]}")
    fi
  done

  if (( ${#issues[@]} == 0 )); then
    add_result "Cloud Run invoker bindings" "PASS" "Expected service-to-service bindings present"
  else
    add_result "Cloud Run invoker bindings" "FAIL" "${issues[*]}"
  fi
}

run_security_tests() {
  if [[ "$SKIP_TESTS" == "true" ]]; then
    add_result "Auth integration tests" "WARN" "Test execution skipped"
    return
  fi
  if ! command -v npm >/dev/null 2>&1; then
    add_result "Auth integration tests" "WARN" "npm not available on PATH"
    return
  fi
  local test_dir="tests/security"
  if [[ ! -d "$test_dir" || ! -f "$test_dir/package.json" ]]; then
    add_result "Auth integration tests" "WARN" "Security test harness missing at ${test_dir}"
    return
  fi
  set +e
  npm --prefix "$test_dir" install --silent >/dev/null 2>&1
  local install_status=$?
  set -e
  if (( install_status != 0 )); then
    add_result "Auth integration tests" "FAIL" "npm install failed in ${test_dir}"
    return
  fi
  set +e
  npm --prefix "$test_dir" test -- --runTestsByPath auth_integration.test.ts >/dev/null 2>&1
  local test_status=$?
  set -e
  if (( test_status == 0 )); then
    add_result "Auth integration tests" "PASS" "Auth and tenant validation tests passed"
  else
    add_result "Auth integration tests" "FAIL" "Auth integration tests failed"
  fi
}

emit_report() {
  local dest="$1"
  local ts
  ts="$(date -u '+%Y-%m-%d %H:%M:%SZ')"
  local header="Security Validation Report"
  local status_str
  if (( OVERALL_STATUS == 0 )); then
    status_str="SUCCESS"
  else
    status_str="FAILURE"
  fi

  local output
  case "$FORMAT" in
    json)
      output=$(REPORT_HEADER="$header" REPORT_TIMESTAMP="$ts" REPORT_STATUS="$status_str" REPORT_RESULTS="$REPORT_RESULTS" PROJECT_ID="$PROJECT_ID" python3 <<'PY'
import json
import os
import sys

header = os.environ.get('REPORT_HEADER')
project_id = os.environ.get('PROJECT_ID')
timestamp = os.environ.get('REPORT_TIMESTAMP')
status = os.environ.get('REPORT_STATUS')
results = os.environ.get('REPORT_RESULTS', '')
items = []
for line in results.splitlines():
    if not line.strip():
        continue
    name, status_item, message = line.split('|', 2)
    items.append({'name': name, 'status': status_item, 'message': message})
report = {
    'title': header,
    'project_id': project_id,
    'generated_at': timestamp,
    'status': status,
    'results': items,
}
json.dump(report, sys.stdout, indent=2)
PY
)
      ;;
    text)
      output=$({
        printf '%s\n' "$header"
        printf 'Project: %s\n' "$PROJECT_ID"
        printf 'Generated: %s\n' "$ts"
        printf 'Status: %s\n\n' "$status_str"
        while IFS='|' read -r name status message; do
          printf '[%s] %s - %s\n' "$status" "$name" "$message"
        done <<<"$REPORT_RESULTS"
      })
      ;;
    *)
      output=$({
        printf '# %s\n\n' "$header"
        printf '- Project: %s\n' "$PROJECT_ID"
        printf '- Generated: %s\n' "$ts"
        printf '- Status: %s\n\n' "$status_str"
        printf '## Findings\n'
        while IFS='|' read -r name status message; do
          printf '- [%s] %s – %s\n' "$status" "$name" "$message"
        done <<<"$REPORT_RESULTS"
      })
      ;;
  esac

  printf '%s\n' "$output" | tee "$dest"
}

check_service_accounts
check_service_roles
check_secrets
check_run_invocations
validate_oauth_credentials
run_security_tests

REPORT_RESULTS=$(printf '%s\n' "${VALIDATION_RESULTS[@]}")

if [[ -z "$OUTPUT_PATH" ]]; then
  local_timestamp="$(date -u '+%Y-%m-%dT%H-%M-%SZ')"
  local extension
  case "$FORMAT" in
    markdown)
      extension="md"
      ;;
    text)
      extension="txt"
      ;;
    json)
      extension="json"
      ;;
    *)
      extension="$FORMAT"
      ;;
  esac
  OUTPUT_PATH="reports/security_validation_${local_timestamp}.${extension}"
fi
mkdir -p "$(dirname "$OUTPUT_PATH")"

REPORT_HEADER="Security Validation Report"
REPORT_TIMESTAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
REPORT_STATUS=$( [[ $OVERALL_STATUS -eq 0 ]] && echo SUCCESS || echo FAILURE )
emit_report "$OUTPUT_PATH"

exit "$OVERALL_STATUS"
