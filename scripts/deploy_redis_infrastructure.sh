#!/usr/bin/env bash

SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Deploy or update the Memorystore Redis instance used by the ECO service.

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BLUE="\033[0;34m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RED="\033[0;31m"; NC="\033[0m"
log()  { echo -e "${BLUE}[deploy-redis]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*" 1>&2; }

PROJECT_ID=${PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}
REGION=${REGION:-${ECO_REDIS_REGION:-${GOOGLE_CLOUD_REGION:-}}}
REDIS_INSTANCE=${REDIS_INSTANCE:-${ECO_REDIS_INSTANCE_NAME:-}}
REDIS_TIER=${REDIS_TIER:-${ECO_REDIS_TIER:-STANDARD_HA}}
REDIS_SIZE_GB=${REDIS_SIZE_GB:-${ECO_REDIS_SIZE_GB:-1}}
REDIS_SECRET_NAME=${REDIS_SECRET_NAME:-${ECO_REDIS_SECRET_NAME:-eco-redis-url}}
REDIS_NETWORK=${REDIS_NETWORK:-${ECO_REDIS_NETWORK:-}}

SKIP_SECRET_STORAGE=$(tr '[:upper:]' '[:lower:]' <<<"${SKIP_SECRET_STORAGE:-false}")

require_env() {
  local var="$1"; local description="$2"
  if [[ -z "${!var:-}" ]]; then
    err "Missing required env var: $var (${description})"
    exit 1
  fi
}

require_env PROJECT_ID "Target Google Cloud project"
require_env REGION "Region for the Memorystore instance"
require_env REDIS_INSTANCE "Memorystore instance name"

ensure_tools() {
  command -v gcloud >/dev/null || { err "gcloud CLI not found"; exit 1; }
}

ensure_instance() {
  log "Ensuring Memorystore Redis instance '${REDIS_INSTANCE}' exists in '${REGION}'"
  if gcloud redis instances describe "$REDIS_INSTANCE" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
    log "Instance exists, applying configuration updates if needed"
    local update_args=(
      "$REDIS_INSTANCE"
      --project="$PROJECT_ID"
      --region="$REGION"
      --size="$REDIS_SIZE_GB"
      --tier="$REDIS_TIER"
    )
    if [[ -n "$REDIS_NETWORK" ]]; then
      update_args+=(--network="$REDIS_NETWORK")
    fi
    gcloud redis instances update "${update_args[@]}" >/dev/null
    ok "Memorystore instance updated"
  else
    log "Creating Memorystore Redis instance"
    local create_args=(
      "$REDIS_INSTANCE"
      --project="$PROJECT_ID"
      --region="$REGION"
      --size="$REDIS_SIZE_GB"
      --tier="$REDIS_TIER"
    )
    if [[ -n "$REDIS_NETWORK" ]]; then
      create_args+=(--network="$REDIS_NETWORK")
    fi
    gcloud redis instances create "${create_args[@]}" >/dev/null
    ok "Memorystore instance created"
  fi
}

store_connection_secret() {
  if [[ "$SKIP_SECRET_STORAGE" == "true" ]]; then
    warn "Skipping Redis secret storage as requested"
    return
  fi

  log "Storing Redis connection endpoint in Secret Manager (${REDIS_SECRET_NAME})"
  local host
  local port
  host=$(gcloud redis instances describe "$REDIS_INSTANCE" --region="$REGION" --project="$PROJECT_ID" --format='value(host)')
  port=$(gcloud redis instances describe "$REDIS_INSTANCE" --region="$REGION" --project="$PROJECT_ID" --format='value(port)')
  local url="redis://${host}:${port}"

  if gcloud secrets describe "$REDIS_SECRET_NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
    printf "%s" "$url" | gcloud secrets versions add "$REDIS_SECRET_NAME" --data-file=- --project="$PROJECT_ID" >/dev/null
  else
    printf "%s" "$url" | gcloud secrets create "$REDIS_SECRET_NAME" --data-file=- --replication-policy=automatic --project="$PROJECT_ID" >/dev/null
  fi
  ok "Redis secret stored"
}

main() {
  ensure_tools
  ensure_instance
  store_connection_secret
  ok "Redis infrastructure deployment complete"
}

main "$@"
