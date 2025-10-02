#!/usr/bin/env bash
set -euo pipefail

# Use Bash 4+ if available for better associative array support
if [[ -x /opt/homebrew/bin/bash ]] && [[ $(/opt/homebrew/bin/bash --version | head -1 | grep -oE '[0-9]+' | head -1) -ge 4 ]]; then
  if [[ "${BASH_VERSION%%.*}" -lt 4 ]]; then
    exec /opt/homebrew/bin/bash "$0" "$@"
  fi
fi

SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

CONFIG_FILE="config/infrastructure/headhunter-production.env"
CLI_PROJECT_ID=""
REGION="us-central1"

# Bash 4+ has proper associative arrays, Bash 3.2 fallback uses encoded strings
if [[ "${BASH_VERSION%%.*}" -ge 4 ]]; then
  declare -A SA_CACHE=()
  declare -A ROTATION_OVERRIDES=()
else
  SA_CACHE=""
  ROTATION_OVERRIDES=""
fi

DEFAULT_ROTATION_SECONDS=7776000
STRICT_MODE=false
STRICT_FAILURE=false
MISSING_SECRET_BINDINGS=""

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--project-id PROJECT_ID] [--config PATH]

Creates Headhunter secrets and binds IAM access for Cloud Run services.
Provide secret material via environment variables named HH_SECRET_<SANITIZED_SECRET_NAME>.
Options:
  --strict             Fail if any secret bindings are missing.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      CLI_PROJECT_ID="$2"
      shift 2
      ;;
    --config)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --strict)
      STRICT_MODE=true
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

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Config file ${CONFIG_FILE} not found" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"
CONFIG_PROJECT_ID="${PROJECT_ID:-}"
PROJECT_ID="${CLI_PROJECT_ID:-${CONFIG_PROJECT_ID}}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "Project ID must be provided" >&2
  exit 1
fi

REQUIRED_SERVICE_ALIASES=(
  SVC_ADMIN
  SVC_ENRICH
  SVC_MSGS
  SVC_SEARCH
  SVC_EVIDENCE
  SVC_ECO
  SVC_EMBED
  SVC_RERANK
)

for var_name in "${REQUIRED_SERVICE_ALIASES[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing configuration value for ${var_name}" >&2
    exit 1
  fi
done

# Compatibility functions for associative arrays (Bash 3.2 vs 4+)
_cache_set() {
  local key="$1" value="$2" varname="$3"
  if [[ "${BASH_VERSION%%.*}" -ge 4 ]]; then
    eval "${varname}[${key}]=${value}"
  else
    eval "${varname}=\"\${${varname}}\${${varname}:+ }${key}=${value}\""
  fi
}

_cache_get() {
  local key="$1" varname="$2"
  if [[ "${BASH_VERSION%%.*}" -ge 4 ]]; then
    eval "echo \"\${${varname}[${key}]:-}\""
  else
    eval "echo \"\${${varname}}\"" | tr ' ' '\n' | grep "^${key}=" | cut -d= -f2
  fi
}

_cache_exists() {
  local key="$1" varname="$2"
  if [[ "${BASH_VERSION%%.*}" -ge 4 ]]; then
    eval "[[ -n \${${varname}[${key}]+x} ]]"
  else
    eval "echo \"\${${varname}}\"" | tr ' ' '\n' | grep -q "^${key}="
  fi
}

_array_append() {
  local value="$1" varname="$2"
  if [[ "${BASH_VERSION%%.*}" -ge 4 ]]; then
    eval "${varname}+=(\"${value}\")"
  else
    eval "${varname}=\"\${${varname}}\${${varname}:+|}${value}\""
  fi
}

_array_length() {
  local varname="$1"
  if [[ "${BASH_VERSION%%.*}" -ge 4 ]]; then
    eval "echo \${#${varname}[@]}"
  else
    local val
    eval "val=\"\${${varname}}\""
    [[ -z "$val" ]] && echo 0 || echo "$val" | tr '|' '\n' | wc -l | tr -d ' '
  fi
}

_array_iterate() {
  local varname="$1"
  if [[ "${BASH_VERSION%%.*}" -ge 4 ]]; then
    eval "for item in \"\${${varname}[@]}\"; do echo \"\$item\"; done"
  else
    eval "echo \"\${${varname}}\"" | tr '|' '\n'
  fi
}

trim() {
  local value="$1"
  value="${value#${value%%[![:space:]]*}}"
  value="${value%${value##*[![:space:]]}}"
  printf '%s' "$value"
}

strip_quotes() {
  local value="$1"
  value="${value#\'}"
  value="${value%\'}"
  value="${value#\"}"
  value="${value%\"}"
  printf '%s' "$value"
}

load_rotation_config() {
  local file line key value cleaned
  for file in config/security/security-*.env; do
    [[ -f "$file" ]] || continue
    while IFS= read -r line || [[ -n "$line" ]]; do
      line="${line%%#*}"
      line=$(trim "$line")
      [[ -z "$line" ]] && continue
      if [[ "$line" == SECRET_ROTATION_PERIOD=* ]]; then
        value=${line#SECRET_ROTATION_PERIOD=}
        value=$(strip_quotes "$(trim "$value")")
        if [[ "$value" =~ ^[0-9]+$ ]]; then
          DEFAULT_ROTATION_SECONDS="$value"
        else
          warn "Ignoring invalid SECRET_ROTATION_PERIOD in ${file}: ${value}"
        fi
        continue
      fi
      if [[ "$line" == SECRET_ROTATION_OVERRIDE_* ]]; then
        key=${line%%=*}
        value=${line#*=}
        key=${key#SECRET_ROTATION_OVERRIDE_}
        cleaned=$(strip_quotes "$(trim "$value")")
        if [[ -n "$key" && "$cleaned" =~ ^[0-9]+$ ]]; then
          _cache_set "$key" "$cleaned" ROTATION_OVERRIDES
        else
          warn "Ignoring invalid rotation override '${line}' in ${file}"
        fi
      fi
    done < "$file"
  done
}

sanitize_secret_env() {
  echo "$1" | tr '[:lower:]' '[:upper:]' | tr '-' '_' | tr '.' '_'
}

log() {
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%S%z')] $*" >&2
}

warn() {
  log "WARN: $*"
}

load_rotation_config

rotation_period_for_secret() {
  local secret="$1"
  local override
  override=$(_cache_get "$secret" ROTATION_OVERRIDES)
  if [[ -n "$override" ]]; then
    printf '%s' "$override"
  else
    printf '%s' "$DEFAULT_ROTATION_SECONDS"
  fi
}

next_rotation_timestamp_seconds() {
  local seconds="$1"
  local ts
  if ts=$(date -u -v+"${seconds}"S '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null); then
    printf '%s' "$ts"
    return
  fi
  if ts=$(date -u -d "+${seconds} seconds" '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null); then
    printf '%s' "$ts"
    return
  fi
  date -u '+%Y-%m-%dT%H:%M:%SZ'
}

apply_rotation_policy() {
  local secret="$1"
  local rotation_seconds
  rotation_seconds=$(rotation_period_for_secret "$secret")
  local next_time
  next_time=$(next_rotation_timestamp_seconds "$rotation_seconds")
  gcloud secrets update "$secret" --project="$PROJECT_ID" \
    --rotation-period="${rotation_seconds}s" \
    --next-rotation-time="$next_time" >/dev/null 2>&1 || true
}

create_secret() {
  local secret=$1
  local description=$2
  if gcloud secrets describe "$secret" --project="$PROJECT_ID" >/dev/null 2>&1; then
    log "Secret ${secret} already exists"
    local replication
    replication=$(gcloud secrets describe "$secret" --project="$PROJECT_ID" --format='value(replication.policy)' 2>/dev/null || true)
    if [[ -n "$replication" && "$replication" != "user-managed" ]]; then
      warn "Secret ${secret} uses ${replication} replication (expected user-managed in ${REGION})"
    fi
  else
    log "Creating secret ${secret}"
    gcloud secrets create "$secret" \
      --project="$PROJECT_ID" \
      --replication-policy=user-managed \
      --locations="$REGION" \
      --data-file=<(echo "placeholder-${secret}") \
      --labels=env=prod,team=headhunter
  fi

  apply_rotation_policy "$secret"

  local env_key="HH_SECRET_$(sanitize_secret_env "$secret")"
  if [[ -n "${!env_key:-}" ]]; then
    log "Publishing provided value for ${secret}"
    printf '%s' "${!env_key}" | gcloud secrets versions add "$secret" \
      --project="$PROJECT_ID" --data-file=- >/dev/null
  fi
}

service_account_email() {
  local alias="$1"
  echo "${alias}@${PROJECT_ID}.iam.gserviceaccount.com"
}

ensure_service_account() {
  local alias="$1"
  [[ -z "$alias" ]] && return 1

  if _cache_exists "$alias" SA_CACHE; then
    local cached_value
    cached_value=$(_cache_get "$alias" SA_CACHE)
    return "$cached_value"
  fi

  local email
  email="$(service_account_email "$alias")"
  if gcloud iam service-accounts describe "$email" --project="$PROJECT_ID" >/dev/null 2>&1; then
    _cache_set "$alias" 0 SA_CACHE
    return 0
  fi

  log "Service account ${email} not found"
  _cache_set "$alias" 1 SA_CACHE
  return 1
}

bind_secret() {
  local secret=$1
  shift
  local missing_accounts=""
  for sa in "$@"; do
    [[ -z "$sa" ]] && continue
    if ensure_service_account "$sa"; then
      gcloud secrets add-iam-policy-binding "$secret" \
        --project="$PROJECT_ID" \
        --member="serviceAccount:$(service_account_email "$sa")" \
        --role="roles/secretmanager.secretAccessor" >/dev/null
    else
      missing_accounts="${missing_accounts}${missing_accounts:+ }${sa}"
    fi
  done

  if [[ -n "$missing_accounts" ]]; then
    local message="${secret}: missing ${missing_accounts}"
    warn "$message"
    _array_append "$message" MISSING_SECRET_BINDINGS
    if [[ "$STRICT_MODE" == "true" ]]; then
      STRICT_FAILURE=true
    fi
  fi

  return 0
}

log "Setting project ${PROJECT_ID}" \
  && gcloud config set project "$PROJECT_ID" >/dev/null

create_secret "$SECRET_DB_PRIMARY" "Primary database credentials"
create_secret "$SECRET_DB_REPLICA" "Replica database credentials"
create_secret "$SECRET_DB_ANALYTICS" "Analytics database credentials"
create_secret "$SECRET_TOGETHER_AI" "Together AI API key"
create_secret "$SECRET_GEMINI_AI" "Gemini API key"
create_secret "$SECRET_OAUTH_CLIENT" "OAuth2 client credentials"
create_secret "$SECRET_REDIS_ENDPOINT" "Redis endpoint URI"
create_secret "$SECRET_STORAGE_SIGNER" "Storage signed URL key"

bind_secret "$SECRET_DB_PRIMARY" "$SVC_ADMIN" "$SVC_ENRICH" "$SVC_MSGS"
bind_secret "$SECRET_DB_REPLICA" "$SVC_SEARCH" "$SVC_EVIDENCE" "$SVC_ECO"
bind_secret "$SECRET_DB_ANALYTICS" "$SVC_ADMIN" "$SVC_ENRICH"
bind_secret "$SECRET_TOGETHER_AI" "$SVC_EMBED" "$SVC_SEARCH" "$SVC_RERANK"
bind_secret "$SECRET_GEMINI_AI" "$SVC_EMBED" "$SVC_SEARCH"
bind_secret "$SECRET_OAUTH_CLIENT" "$SVC_ADMIN" "$SVC_ENRICH"
bind_secret "$SECRET_REDIS_ENDPOINT" "$SVC_EMBED" "$SVC_SEARCH" "$SVC_MSGS" "$SVC_EVIDENCE" "$SVC_ECO" "$SVC_ENRICH"
bind_secret "$SECRET_STORAGE_SIGNER" "$SVC_ADMIN" "$SVC_ENRICH"

if (( $(_array_length MISSING_SECRET_BINDINGS) > 0 )); then
  warn "Secret bindings skipped:"
  while IFS= read -r entry; do
    [[ -z "$entry" ]] && continue
    warn "  ${entry}"
  done < <(_array_iterate MISSING_SECRET_BINDINGS)
fi

if [[ "$STRICT_MODE" == "true" && "$STRICT_FAILURE" == "true" ]]; then
  log "Strict mode enabled and missing bindings detected; exiting with failure"
  exit 1
fi

log "Secret Manager setup complete"
