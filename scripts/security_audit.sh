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
ENVIRONMENT="production"

timestamp_utc() {
  date -u '+%Y-%m-%dT%H:%M:%SZ'
}

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Options:
  --project-id ID       Target GCP project id
  --config PATH         Infrastructure config (default: ${CONFIG_PATH})
  --output PATH         Write audit report to file
  --format FORMAT       Report format: markdown|text|json (default: markdown)
  --environment NAME    Deployment environment suffix (default: production)
  -h, --help            Show this message
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

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command '$1' not found" >&2
    exit 2
  fi
}

require_command gcloud
require_command jq

CLI_PROJECT_ID="$PROJECT_ID"

# shellcheck disable=SC1090
source "$CONFIG_PATH"

CONFIG_PROJECT_ID="${PROJECT_ID:-}"
PROJECT_ID="${CLI_PROJECT_ID:-${CONFIG_PROJECT_ID}}"
if [[ -z "$PROJECT_ID" ]]; then
  echo "Project ID must be provided via --project-id or config" >&2
  exit 1
fi

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

service_account_email() {
  echo "$1@${PROJECT_ID}.iam.gserviceaccount.com"
}

log_tmp_dir="$(mktemp -d)"
trap 'rm -rf "$log_tmp_dir"' EXIT

gcloud config set project "$PROJECT_ID" >/dev/null 2>&1 || true

# Run baseline validation -----------------------------------------------------
VALIDATION_JSON="${log_tmp_dir}/validation.json"
./scripts/validate_security_setup.sh \
  --project-id "$PROJECT_ID" \
  --config "$CONFIG_PATH" \
  --format json \
  --output "$VALIDATION_JSON" >/dev/null

VALIDATION_RESULTS=$(jq -c '.results' "$VALIDATION_JSON")
VALIDATION_STATUS=$(jq -r '.status' "$VALIDATION_JSON")

# Expected role mapping (align with IAM script)
declare -A EXPECTED_ROLES
EXPECTED_ROLES["$SVC_EMBED"]="roles/cloudsql.client roles/redis.viewer roles/aiplatform.user roles/secretmanager.secretAccessor"
EXPECTED_ROLES["$SVC_SEARCH"]="roles/cloudsql.client roles/redis.viewer roles/secretmanager.secretAccessor"
EXPECTED_ROLES["$SVC_RERANK"]="roles/redis.viewer roles/secretmanager.secretAccessor"
EXPECTED_ROLES["$SVC_EVIDENCE"]="roles/cloudsql.client roles/datastore.viewer roles/redis.viewer roles/secretmanager.secretAccessor"
EXPECTED_ROLES["$SVC_ECO"]="roles/cloudsql.client roles/datastore.viewer roles/redis.viewer roles/secretmanager.secretAccessor"
EXPECTED_ROLES["$SVC_ENRICH"]="roles/cloudsql.client roles/datastore.user roles/pubsub.publisher roles/pubsub.subscriber roles/secretmanager.secretAccessor"
EXPECTED_ROLES["$SVC_ADMIN"]="roles/cloudsql.client roles/pubsub.publisher roles/pubsub.subscriber roles/monitoring.viewer roles/logging.logWriter roles/secretmanager.secretAccessor"
EXPECTED_ROLES["$SVC_MSGS"]="roles/cloudsql.client roles/redis.viewer roles/secretmanager.secretAccessor"

# Secret access expectations
expected_secret_members() {
  local secret="$1"
  case "$secret" in
    "$SECRET_DB_PRIMARY") echo "$SVC_ADMIN $SVC_ENRICH $SVC_MSGS" ;;
    "$SECRET_DB_REPLICA") echo "$SVC_SEARCH $SVC_EVIDENCE $SVC_ECO" ;;
    "$SECRET_DB_ANALYTICS") echo "$SVC_ADMIN $SVC_ENRICH" ;;
    "$SECRET_TOGETHER_AI") echo "$SVC_EMBED $SVC_SEARCH $SVC_RERANK" ;;
    "$SECRET_GEMINI_AI") echo "$SVC_EMBED $SVC_SEARCH" ;;
    "$SECRET_OAUTH_CLIENT") echo "$SVC_ADMIN $SVC_ENRICH" ;;
    "$SECRET_REDIS_ENDPOINT") echo "$SVC_EMBED $SVC_SEARCH $SVC_MSGS $SVC_EVIDENCE $SVC_ECO $SVC_ENRICH" ;;
    "$SECRET_STORAGE_SIGNER") echo "$SVC_ADMIN $SVC_ENRICH" ;;
    *) echo "" ;;
  esac
}

# Helper to capture unexpected IAM roles -------------------------------------
project_policy=$(gcloud projects get-iam-policy "$PROJECT_ID" --format=json)
overprivileged_entries=()
for alias in "${SERVICE_ALIASES[@]}"; do
  [[ -z "$alias" ]] && continue
  expected_roles_string="${EXPECTED_ROLES[$alias]:-}"
  expected_roles=( $expected_roles_string )
  declare -A expected_lookup=()
  for role in "${expected_roles[@]}"; do
    expected_lookup[$role]=1
  done
  email=$(service_account_email "$alias")
  member="serviceAccount:${email}"
  assigned_roles=$(jq -r --arg member "$member" '.bindings[] | select(.members[]? == $member) | .role' <<<"$project_policy")
  while IFS= read -r role; do
    [[ -z "$role" ]] && continue
    if [[ -z "${expected_lookup[$role]:-}" ]]; then
      overprivileged_entries+=("${alias}:${role}")
    fi
  done <<<"$assigned_roles"
  unset expected_lookup
done

# Identify unexpected Secret Manager bindings --------------------------------
secret_policy_issues=()
for secret in "${SECRETS[@]}"; do
  [[ -z "$secret" ]] && continue
  if ! gcloud secrets describe "$secret" >/dev/null 2>&1; then
    continue
  fi
  policy=$(gcloud secrets get-iam-policy "$secret" --format=json 2>/dev/null || true)
  [[ -z "$policy" ]] && continue
  expected_aliases=( $(expected_secret_members "$secret") )
  declare -A expected_members=()
  for alias in "${expected_aliases[@]}"; do
    expected_members["serviceAccount:$(service_account_email "$alias")"]=1
  done
  mapfile -t members < <(jq -r '.bindings[] | select(.role == "roles/secretmanager.secretAccessor") | .members[]?' <<<"$policy")
  for member in "${members[@]}"; do
    if [[ -z "${expected_members[$member]:-}" ]]; then
      secret_policy_issues+=("${secret}:${member}")
    fi
  done
  unset expected_members
done

# Check for public Cloud Run services ----------------------------------------
public_run_services=()
declare -A run_services
run_services["${RUN_SERVICE_EMBED:-}"]=true
run_services["${RUN_SERVICE_SEARCH:-}"]=true
run_services["${RUN_SERVICE_RERANK:-}"]=true
run_services["${RUN_SERVICE_EVIDENCE:-}"]=true
run_services["${RUN_SERVICE_ECO:-}"]=true
run_services["${RUN_SERVICE_ENRICH:-}"]=true
run_services["${RUN_SERVICE_ADMIN:-}"]=true
run_services["${RUN_SERVICE_MSGS:-}"]=true

for service in "${!run_services[@]}"; do
  [[ -z "$service" ]] && continue
  service_name="${service}-${ENVIRONMENT}"
  policy=$(gcloud run services get-iam-policy "$service_name" --region "$REGION_DEFAULT" --project "$PROJECT_ID" --format=json 2>/dev/null || true)
  [[ -z "$policy" ]] && continue
  if jq -e '.bindings[] | select(.role=="roles/run.invoker") | .members[]? | select(.=="allUsers" or .=="allAuthenticatedUsers")' <<<"$policy" >/dev/null 2>&1; then
    public_run_services+=("${service_name}")
  fi
done

# Audit logging configuration -------------------------------------------------
audit_sink="hh-audit-${ENVIRONMENT}"
metric_name="projects/${PROJECT_ID}/metrics/hh-security-events-${ENVIRONMENT}"
missing_audit_artifacts=()
if ! gcloud logging sinks describe "$audit_sink" >/dev/null 2>&1; then
  missing_audit_artifacts+=("missing logging sink ${audit_sink}")
fi
if ! gcloud logging metrics describe "hh-security-events-${ENVIRONMENT}" >/dev/null 2>&1; then
  missing_audit_artifacts+=("missing logging metric hh-security-events-${ENVIRONMENT}")
fi

# Compose report --------------------------------------------------------------
STATUS_CODE=0
if (( ${#overprivileged_entries[@]} > 0 || ${#secret_policy_issues[@]} > 0 || ${#public_run_services[@]} > 0 || ${#missing_audit_artifacts[@]} > 0 )); then
  STATUS_CODE=1
fi

header="Security Audit Report"
timestamp="$(timestamp_utc)"

emit_markdown() {
  printf '# %s\n\n' "$header"
  printf '- Project: %s\n' "$PROJECT_ID"
  printf '- Generated: %s\n' "$timestamp"
  printf '- Validation status: %s\n\n' "$VALIDATION_STATUS"

  printf '## Baseline Validation\n'
  printf '\n'
  printf '| Check | Status | Message |\n'
  printf '|-------|--------|---------|\n'
  echo "$VALIDATION_RESULTS" | jq -r '.[] | "| \(.name) | \(.status) | \(.message) |"'
  printf '\n'

  printf '## Over-privileged IAM Bindings\n\n'
  if (( ${#overprivileged_entries[@]} == 0 )); then
    printf 'No unexpected project-level IAM roles detected for service accounts.\n\n'
  else
    for entry in "${overprivileged_entries[@]}"; do
      printf '- `%s`\n' "$entry"
    done
    printf '\n'
  fi

  printf '## Secret Manager Access Review\n\n'
  if (( ${#secret_policy_issues[@]} == 0 )); then
    printf 'Secret access bindings align with expectations.\n\n'
  else
    for issue in "${secret_policy_issues[@]}"; do
      printf '- `%s`\n' "$issue"
    done
    printf '\n'
  fi

  printf '## Cloud Run Exposure\n\n'
  if (( ${#public_run_services[@]} == 0 )); then
    printf 'No services grant `allUsers` or `allAuthenticatedUsers` invoker access.\n\n'
  else
    printf 'The following services are publicly invokable:\n'
    for svc in "${public_run_services[@]}"; do
      printf '- `%s`\n' "$svc"
    done
    printf '\n'
  fi

  printf '## Audit Instrumentation\n\n'
  if (( ${#missing_audit_artifacts[@]} == 0 )); then
    printf 'Required audit sinks and metrics are present.\n'
  else
    for item in "${missing_audit_artifacts[@]}"; do
      printf '- %s\n' "$item"
    done
    printf '\n'
  fi
}

emit_text() {
  printf '%s\n' "$header"
  printf 'Project: %s\n' "$PROJECT_ID"
  printf 'Generated: %s\n' "$timestamp"
  printf 'Validation status: %s\n\n' "$VALIDATION_STATUS"

  echo "$VALIDATION_RESULTS" | jq -r '.[] | sprintf("[%-4s] %s - %s", .status, .name, .message)'
  printf '\nOver-privileged IAM roles:\n'
  if (( ${#overprivileged_entries[@]} == 0 )); then
    printf '  None\n'
  else
    for entry in "${overprivileged_entries[@]}"; do
      printf '  %s\n' "$entry"
    done
  fi
  printf '\nSecret Manager anomalies:\n'
  if (( ${#secret_policy_issues[@]} == 0 )); then
    printf '  None\n'
  else
    for issue in "${secret_policy_issues[@]}"; do
      printf '  %s\n' "$issue"
    done
  fi
  printf '\nPublic Cloud Run services:\n'
  if (( ${#public_run_services[@]} == 0 )); then
    printf '  None\n'
  else
    for svc in "${public_run_services[@]}"; do
      printf '  %s\n' "$svc"
    done
  fi
  printf '\nAudit instrumentation gaps:\n'
  if (( ${#missing_audit_artifacts[@]} == 0 )); then
    printf '  None\n'
  else
    for item in "${missing_audit_artifacts[@]}"; do
      printf '  %s\n' "$item"
    done
  fi
}

emit_json() {
  jq -n \
    --arg project "$PROJECT_ID" \
    --arg generated "$timestamp" \
    --arg status "$VALIDATION_STATUS" \
    --argjson validation "$VALIDATION_RESULTS" \
    --argjson overprivileged "$(printf '%s\n' "${overprivileged_entries[@]}" | jq -R . | jq -s .)" \
    --argjson secret_issues "$(printf '%s\n' "${secret_policy_issues[@]}" | jq -R . | jq -s .)" \
    --argjson public_services "$(printf '%s\n' "${public_run_services[@]}" | jq -R . | jq -s .)" \
    --argjson audit_gaps "$(printf '%s\n' "${missing_audit_artifacts[@]}" | jq -R . | jq -s .)" \
    '{project: $project, generated_at: $generated, validation_status: $status, validation: $validation,
      overprivileged_roles: $overprivileged, secret_policy_issues: $secret_issues,
      public_run_services: $public_services, audit_gaps: $audit_gaps}'
}

case "$FORMAT" in
  markdown)
    report_output=$(emit_markdown)
    ;;
  text)
    report_output=$(emit_text)
    ;;
  json)
    report_output=$(emit_json)
    ;;
  *)
    echo "Unsupported format: $FORMAT" >&2
    exit 1
    ;;
esac

if [[ -z "$OUTPUT_PATH" ]]; then
  extension="md"
  case "$FORMAT" in
    json) extension="json" ;;
    text) extension="txt" ;;
    markdown) extension="md" ;;
  esac
  OUTPUT_PATH="reports/security_audit_${timestamp//[: ]/_}.${extension}"
fi
mkdir -p "$(dirname "$OUTPUT_PATH")"
printf '%s\n' "$report_output" | tee "$OUTPUT_PATH" >/dev/null

echo "Audit report written to ${OUTPUT_PATH}" >&2
exit "$STATUS_CODE"
