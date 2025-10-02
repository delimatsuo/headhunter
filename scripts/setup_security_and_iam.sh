#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

CONFIG_PATH="config/infrastructure/headhunter-production.env"
ENVIRONMENT="production"
REPORT_DIR="reports"
REPORT_FILE=""
AUTO_ROLLBACK=false
PROJECT_ID=""
IDP_DOMAIN=""
IDP_CLIENT_ID=""
IDP_CLIENT_SECRET=""
IDP_AUDIENCE=""
IDP_SCOPES=""
STEP_NOTE=""
VALIDATION_REPORT_PATH=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Options:
  --config PATH               Path to infrastructure config (default: ${CONFIG_PATH})
  --environment NAME          Deployment environment (default: production)
  --project-id ID             Override GCP project id
  --report PATH               Write orchestrator report to custom location
  --report-dir PATH           Directory for generated report (default: reports)
  --auto-rollback             Execute registered rollback commands on failure
  --idp-domain DOMAIN         Identity provider base domain (required for OAuth provisioning)
  --idp-client-id ID          IdP management client id
  --idp-client-secret SECRET  IdP management client secret
  --idp-audience AUDIENCE     Audience identifier for OAuth client grants
  --idp-scopes SCOPES         Comma-separated OAuth scopes
  --skip-validation           Skip post-setup validation step (not recommended)
  -h, --help                  Show this help message
USAGE
}

SKIP_VALIDATION=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --project-id)
      PROJECT_ID="$2"
      shift 2
      ;;
    --report)
      REPORT_FILE="$2"
      shift 2
      ;;
    --report-dir)
      REPORT_DIR="$2"
      shift 2
      ;;
    --auto-rollback)
      AUTO_ROLLBACK=true
      shift
      ;;
    --idp-domain)
      IDP_DOMAIN="$2"
      shift 2
      ;;
    --idp-client-id)
      IDP_CLIENT_ID="$2"
      shift 2
      ;;
    --idp-client-secret)
      IDP_CLIENT_SECRET="$2"
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
    --skip-validation)
      SKIP_VALIDATION=true
      shift
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
  echo "Project ID must be specified via --project-id or in the config file" >&2
  exit 1
fi

if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
  echo "Environment must be staging or production" >&2
  exit 1
fi

log() {
  printf '[setup-security][%s] %s\n' "$(date -Is)" "$*"
}

warn() {
  log "WARN: $*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command '$1' not found in PATH" >&2
    exit 1
  fi
}

require_command gcloud
require_command jq
require_command python3
require_command bash
require_command awk

log "Using project ${PROJECT_ID} (${ENVIRONMENT})"

gcloud config set project "$PROJECT_ID" >/dev/null 2>&1 || true

mkdir -p "$REPORT_DIR"

if [[ -z "${SVC_EMBED:-}" || -z "${SVC_SEARCH:-}" || -z "${SVC_RERANK:-}" || -z "${SVC_EVIDENCE:-}" || -z "${SVC_ECO:-}" || -z "${SVC_ENRICH:-}" || -z "${SVC_ADMIN:-}" || -z "${SVC_MSGS:-}" ]]; then
  echo "Service account aliases must be defined in ${CONFIG_PATH}" >&2
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

ensure_required_services() {
  local required_services=(
    iam.googleapis.com
    run.googleapis.com
    secretmanager.googleapis.com
    aiplatform.googleapis.com
    sqladmin.googleapis.com
    pubsub.googleapis.com
    cloudresourcemanager.googleapis.com
    serviceusage.googleapis.com
    firestore.googleapis.com
    logging.googleapis.com
    monitoring.googleapis.com
  )

  local enabled
  enabled=$(gcloud services list --enabled --project "$PROJECT_ID" --format 'value(config.name)')
  local missing=()
  local service
  for service in "${required_services[@]}"; do
    if ! grep -Fxq "$service" <<<"$enabled"; then
      missing+=("$service")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    log "Enabling missing APIs: ${missing[*]}"
    if ! gcloud services enable "${missing[@]}" --project "$PROJECT_ID"; then
      echo "Failed to enable required services: ${missing[*]}" >&2
      exit 1
    fi
  else
    log "All prerequisite APIs already enabled"
  fi
}

ensure_required_services

declare -a STEP_SUMMARY=()
declare -a ROLLBACK_ACTIONS=()
declare -a MISSING_SERVICE_ACCOUNTS=()
declare -a MISSING_SECRETS=()
declare -a PRE_EXISTING_OAUTH_SECRETS=()
declare -a POST_OAUTH_SECRETS=()
CURRENT_STEP=""

service_account_email() {
  echo "$1@${PROJECT_ID}.iam.gserviceaccount.com"
}

discover_missing_service_accounts() {
  MISSING_SERVICE_ACCOUNTS=()
  for alias in "${SERVICE_ALIASES[@]}"; do
    local email
    email="$(service_account_email "$alias")"
    if ! gcloud iam service-accounts describe "$email" >/dev/null 2>&1; then
      MISSING_SERVICE_ACCOUNTS+=("$email")
    fi
  done
  log "Identified ${#MISSING_SERVICE_ACCOUNTS[@]} service account(s) to create"
}

discover_missing_secrets() {
  MISSING_SECRETS=()
  for secret in "${SECRETS[@]}"; do
    if [[ -z "$secret" ]]; then
      continue
    fi
    if ! gcloud secrets describe "$secret" >/dev/null 2>&1; then
      MISSING_SECRETS+=("$secret")
    fi
  done
  log "Identified ${#MISSING_SECRETS[@]} secret(s) to create"
}

list_oauth_secrets() {
  gcloud secrets list --filter="name~^projects/${PROJECT_ID}/secrets/oauth-client-" \
    --format="value(name)" \
    | awk -F'/' 'NF {print $NF}'
}

register_rollback() {
  local description="$1"
  shift
  local command="${*:-}"
  ROLLBACK_ACTIONS=("${description}:::${command}" "${ROLLBACK_ACTIONS[@]}")
}

execute_rollback() {
  if [[ ${#ROLLBACK_ACTIONS[@]} -eq 0 ]]; then
    return
  fi
  warn "Executing rollback workflow (${#ROLLBACK_ACTIONS[@]} step(s))"
  for entry in "${ROLLBACK_ACTIONS[@]}"; do
    IFS=':::' read -r description command <<<"$entry"
    if [[ "$AUTO_ROLLBACK" == "true" && -n "$command" ]]; then
      log "Rollback: ${description}"
      bash -c "$command" || warn "Rollback command failed: ${command}"
    else
      warn "Rollback required: ${description}${command:+ -> $command}"
    fi
  done
}

run_step() {
  local name="$1"
  shift
  CURRENT_STEP="$name"
  STEP_NOTE=""
  log "Starting ${name}"
  set +e
  "$@"
  local status=$?
  local note="$STEP_NOTE"
  set -e
  if (( status == 0 )); then
    log "Completed ${name}"
    STEP_SUMMARY+=("${name}|SUCCESS|${note}")
    return 0
  fi
  warn "${name} failed (exit code ${status})"
  STEP_SUMMARY+=("${name}|FAILED|${note}")
  return $status
}

handle_failure() {
  local exit_code="$1"
  warn "Setup failed during step '${CURRENT_STEP}'"
  execute_rollback
  generate_report "FAILED"
  exit "$exit_code"
}

generate_report() {
  local final_status="$1"
  local timestamp
  timestamp="$(date -u '+%Y-%m-%dT%H-%M-%SZ')"
  mkdir -p "$REPORT_DIR"
  if [[ -z "$REPORT_FILE" ]]; then
    REPORT_FILE="${REPORT_DIR}/security_setup_${timestamp}.md"
  else
    mkdir -p "$(dirname "$REPORT_FILE")"
  fi
  {
    echo "# Security and IAM Setup Report"
    echo ""
    echo "- Project: ${PROJECT_ID}"
    echo "- Environment: ${ENVIRONMENT}"
    echo "- Completed: $(date -u '+%Y-%m-%d %H:%M:%SZ')"
    echo "- Status: ${final_status}"
    echo ""
    echo "## Steps"
    for entry in "${STEP_SUMMARY[@]}"; do
      IFS='|' read -r step status note <<<"$entry"
      if [[ -n "$note" ]]; then
        echo "- ${step}: ${status} (${note})"
      else
        echo "- ${step}: ${status}"
      fi
    done
    if [[ -n "$VALIDATION_REPORT_PATH" ]]; then
      echo ""
      echo "## Validation Report"
      echo "Validation details: ${VALIDATION_REPORT_PATH}"
    fi
    if [[ ${#ROLLBACK_ACTIONS[@]} -gt 0 ]]; then
      echo ""
      echo "## Rollback Plan"
      for entry in "${ROLLBACK_ACTIONS[@]}"; do
        IFS=':::' read -r description command <<<"$entry"
        if [[ -n "$command" ]]; then
          echo "- ${description}: ${command}"
        else
          echo "- ${description}"
        fi
      done
    fi
  } >"$REPORT_FILE"
  log "Report written to ${REPORT_FILE}"
}

# Step functions -------------------------------------------------------------

iam_setup_step() {
  set +e
  PROJECT_ID="$PROJECT_ID" ./scripts/setup_service_iam.sh "$ENVIRONMENT"
  local status=$?
  set -e
  if (( status == 0 )); then
    STEP_NOTE="Service IAM configured"
  fi
  return $status
}

secret_manager_step() {
  set +e
  ./scripts/setup_secret_manager_headhunter.sh --project-id "$PROJECT_ID" --config "$CONFIG_PATH"
  local status=$?
  set -e
  if (( status == 0 )); then
    STEP_NOTE="Secrets ensured"
  fi
  return $status
}

oauth_provision_step() {
  if [[ -z "$IDP_DOMAIN" || -z "$IDP_CLIENT_ID" || -z "$IDP_CLIENT_SECRET" ]]; then
    warn "IdP configuration missing; cannot provision OAuth2 clients"
    return 1
  fi
  local scopes_env="$IDP_SCOPES"
  set +e
  PROJECT_ID="$PROJECT_ID" \
  IDP_DOMAIN="$IDP_DOMAIN" \
  IDP_MGMT_CLIENT_ID="$IDP_CLIENT_ID" \
  IDP_MGMT_CLIENT_SECRET="$IDP_CLIENT_SECRET" \
  IDP_DEFAULT_AUDIENCE="${IDP_AUDIENCE:-https://api.ella.jobs/gateway}" \
  IDP_ALLOWED_SCOPES="$scopes_env" \
    ./scripts/configure_oauth2_clients.sh provision
  local status=$?
  set -e
  if (( status == 0 )); then
    STEP_NOTE="OAuth2 clients provisioned"
  fi
  return $status
}

validation_step() {
  if [[ "$SKIP_VALIDATION" == "true" ]]; then
    STEP_NOTE="Validation skipped"
    return 0
  fi
  local validation_output
  local output_path
  output_path="${REPORT_DIR}/security_validation_$(date -u '+%Y-%m-%dT%H-%M-%SZ').md"
  set +e
  validation_output=$(./scripts/validate_security_setup.sh \
    --project-id "$PROJECT_ID" \
    --config "$CONFIG_PATH" \
    --output "$output_path")
  local status=$?
  set -e
  if (( status == 0 )); then
    VALIDATION_REPORT_PATH="$output_path"
    STEP_NOTE="Validation report at ${output_path}"
    printf '%s\n' "$validation_output"
  fi
  return $status
}

# ---------------------------------------------------------------------------

discover_missing_service_accounts
pre_oauth_secrets=$(list_oauth_secrets || true)
PRE_EXISTING_OAUTH_SECRETS=()
if [[ -n "$pre_oauth_secrets" ]]; then
  readarray -t PRE_EXISTING_OAUTH_SECRETS <<<"$pre_oauth_secrets"
fi

discover_missing_secrets

if run_step "Service IAM" iam_setup_step; then
  if [[ ${#MISSING_SERVICE_ACCOUNTS[@]} -gt 0 ]]; then
    for email in "${MISSING_SERVICE_ACCOUNTS[@]}"; do
      register_rollback "Delete service account ${email}" "gcloud iam service-accounts delete ${email} --quiet --project=${PROJECT_ID}"
    done
  fi
else
  handle_failure $?
fi

if run_step "Secret Manager" secret_manager_step; then
  if [[ ${#MISSING_SECRETS[@]} -gt 0 ]]; then
    for secret in "${MISSING_SECRETS[@]}"; do
      register_rollback "Delete secret ${secret}" "gcloud secrets delete ${secret} --quiet --project=${PROJECT_ID}"
    done
  fi
else
  handle_failure $?
fi

if run_step "OAuth2 Provisioning" oauth_provision_step; then
  post_oauth_secrets=$(list_oauth_secrets || true)
  POST_OAUTH_SECRETS=()
  if [[ -n "$post_oauth_secrets" ]]; then
    readarray -t POST_OAUTH_SECRETS <<<"$post_oauth_secrets"
  fi
  if [[ ${#POST_OAUTH_SECRETS[@]} -gt ${#PRE_EXISTING_OAUTH_SECRETS[@]} ]]; then
    for secret_name in "${POST_OAUTH_SECRETS[@]}"; do
      if [[ " ${PRE_EXISTING_OAUTH_SECRETS[*]} " != *" ${secret_name} "* ]]; then
        register_rollback "Delete OAuth secret ${secret_name}" "gcloud secrets delete ${secret_name} --quiet --project=${PROJECT_ID}"
      fi
    done
  fi
else
  handle_failure $?
fi

if run_step "Validation" validation_step; then
  :
else
  handle_failure $?
fi

generate_report "SUCCESS"
log "Security and IAM orchestration completed"
