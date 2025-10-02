#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

usage() {
  cat <<'USAGE'
Usage: scripts/update-gateway-routes.sh [options]

Updates API Gateway routes to target the latest Cloud Run service URLs.

Options:
  --project-id <id>        Google Cloud project ID
  --environment <env>      Deployment environment label (default: production)
  --manifest <path>        Deployment manifest generated from Cloud Run step
  --gateway-id <id>        Gateway identifier (default: headhunter-api-gateway-<env>)
  --skip-validation        Skip post-update validation scripts
  --dry-run                Render configuration without applying changes
  -h, --help               Show this help message
USAGE
}

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

warn() {
  printf '[%s] WARN: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
}

fail() {
  printf '[%s] ERROR: %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
  exit 1
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "Required command '$1' not found in PATH."
  fi
}

to_env_key() {
  local name="$1"
  name="${name//-/_}"
  printf '%s' "${name^^}"
}

PROJECT_ID="${PROJECT_ID:-}"
ENVIRONMENT="${ENVIRONMENT:-production}"
DEPLOYMENT_MANIFEST=""
GATEWAY_ID=""
SKIP_VALIDATION=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id)
      PROJECT_ID="$2"; shift 2 ;;
    --environment)
      ENVIRONMENT="$2"; shift 2 ;;
    --manifest)
      DEPLOYMENT_MANIFEST="$2"; shift 2 ;;
    --gateway-id)
      GATEWAY_ID="$2"; shift 2 ;;
    --skip-validation)
      SKIP_VALIDATION=true; shift ;;
    --dry-run)
      DRY_RUN=true; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      fail "Unknown argument: $1" ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

require_command gcloud
require_command jq
require_command python3

CONFIG_FILE="config/infrastructure/headhunter-${ENVIRONMENT}.env"
if [[ ! -f "$CONFIG_FILE" ]]; then
  if [[ "$ENVIRONMENT" != "production" ]]; then
    warn "Configuration file ${CONFIG_FILE} not found; falling back to production config."
  fi
  CONFIG_FILE="config/infrastructure/headhunter-production.env"
fi
if [[ ! -f "$CONFIG_FILE" ]]; then
  fail "Infrastructure configuration file not found."
fi

CLI_PROJECT_ID="$PROJECT_ID"
set -a
source "$CONFIG_FILE"
set +a

if [[ -n "$CLI_PROJECT_ID" ]]; then
  PROJECT_ID="$CLI_PROJECT_ID"
fi

if [[ -z "$PROJECT_ID" ]]; then
  fail "Project ID could not be determined. Provide via --project-id or config."
fi

REGION="${REGION:-us-central1}"
if [[ -z "$GATEWAY_ID" ]]; then
  GATEWAY_ID="headhunter-api-gateway-${ENVIRONMENT}"
fi

if [[ -z "$DEPLOYMENT_MANIFEST" ]]; then
  fail "Deployment manifest is required via --manifest."
fi
if [[ ! -f "$DEPLOYMENT_MANIFEST" ]]; then
  fail "Deployment manifest not found at ${DEPLOYMENT_MANIFEST}."
fi

log "Updating API Gateway ${GATEWAY_ID} using manifest ${DEPLOYMENT_MANIFEST}"

# Load service URLs from manifest
SERVICES=(
  hh-embed-svc
  hh-search-svc
  hh-rerank-svc
  hh-evidence-svc
  hh-eco-svc
  hh-msgs-svc
  hh-admin-svc
  hh-enrich-svc
)
declare -A SERVICE_URLS
for svc in "${SERVICES[@]}"; do
  url=$(jq -r --arg svc "$svc" '.services[] | select(.service==$svc) | .url // empty' "$DEPLOYMENT_MANIFEST")
  if [[ -z "$url" ]]; then
    warn "Service ${svc} missing URL in manifest; gateway config may be incomplete."
    continue
  fi
  SERVICE_URLS[$svc]="$url"
  export "$(to_env_key "$svc")_URL"="$url"
  export "$(to_env_key "$svc")_JWT_AUDIENCE"="$url"
  log "Resolved ${svc} -> ${url}"
done

TEMPLATE="docs/openapi/gateway.yaml"
if [[ ! -f "$TEMPLATE" ]]; then
  fail "Gateway template ${TEMPLATE} not found."
fi

render_gateway_spec() {
  local output="$(mktemp)"
  local services_list="${SERVICES[*]}"
  python3 - <<'PY' "$TEMPLATE" "$output" "$ENVIRONMENT" "$PROJECT_ID" "$REGION" "$services_list"
import os
import sys
from pathlib import Path

template_path, output_path, environment, project_id, region, services_csv = sys.argv[1:7]
services = services_csv.split()
text = Path(template_path).read_text()

# Replace backend addresses with actual URLs
for svc in services:
    url = os.environ.get(f"{svc.replace('-', '_').upper()}_URL")
    if not url:
        continue
    placeholder = f"https://${{REGION}}-run.googleapis.com/apis/serving.knative.dev/v1/namespaces/${{PROJECT_ID}}/services/{svc}-${{ENVIRONMENT}}"
    text = text.replace(f"address: {placeholder}", f"address: {url}")
    text = text.replace(f"jwt_audience: {placeholder}", f"jwt_audience: {url}")

replacements = {
    '${ENVIRONMENT}': environment,
    '${PROJECT_ID}': project_id,
    '${REGION}': region,
}
for key, value in replacements.items():
    text = text.replace(key, value)

Path(output_path).write_text(text)
PY
  printf '%s' "$output"
}

RENDERED_SPEC=$(render_gateway_spec)

TIMESTAMP="$(date -u +'%Y%m%d-%H%M%S')"
DEPLOYMENT_DIR="${PROJECT_ROOT}/.deployment"
mkdir -p "$DEPLOYMENT_DIR"
GATEWAY_SNAPSHOT="${DEPLOYMENT_DIR}/gateway-config-${TIMESTAMP}.yaml"
cp "$RENDERED_SPEC" "$GATEWAY_SNAPSHOT"

if [[ "$DRY_RUN" == true ]]; then
  log "Dry-run mode: rendered gateway spec at ${GATEWAY_SNAPSHOT}"
  log "Skipping gateway deployment due to dry-run."
  rm -f "$RENDERED_SPEC"
  exit 0
fi

log "Applying gateway configuration via deploy_api_gateway.sh"
ENVIRONMENT="$ENVIRONMENT" \
PROJECT_ID="$PROJECT_ID" \
REGION="$REGION" \
GATEWAY_ID="$GATEWAY_ID" \
OPENAPI_SPEC="$RENDERED_SPEC" \
bash "$SCRIPT_DIR/deploy_api_gateway.sh"

rm -f "$RENDERED_SPEC"

GATEWAY_HOST=$(gcloud api-gateway gateways describe "$GATEWAY_ID" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --format="value(defaultHostname)")
if [[ -z "$GATEWAY_HOST" ]]; then
  warn "Could not determine gateway hostname."
fi

SUMMARY_LOG="${DEPLOYMENT_DIR}/gateway-update-summary-${TIMESTAMP}.log"
{
  printf 'Gateway ID: %s\n' "$GATEWAY_ID"
  printf 'Region: %s\n' "$REGION"
  printf 'Environment: %s\n' "$ENVIRONMENT"
  printf 'Manifest: %s\n' "$DEPLOYMENT_MANIFEST"
  printf 'Config Snapshot: %s\n' "$GATEWAY_SNAPSHOT"
  printf 'Gateway Host: %s\n' "${GATEWAY_HOST:-unknown}"
  printf 'Service Routes:\n'
  for svc in "${SERVICES[@]}"; do
    printf '  %s -> %s\n' "$svc" "${SERVICE_URLS[$svc]:-unresolved}"
  done
} >"$SUMMARY_LOG"

if [[ "$SKIP_VALIDATION" == false ]]; then
  if [[ -n "$GATEWAY_HOST" ]]; then
    GATEWAY_ENDPOINT="https://${GATEWAY_HOST}"
    log "Running gateway routing validation against ${GATEWAY_ENDPOINT}"
    if ! "$SCRIPT_DIR/test_gateway_routing.sh" --endpoint "$GATEWAY_ENDPOINT" --environment "$ENVIRONMENT" --project "$PROJECT_ID" --mode smoke; then
      warn "Gateway routing validation encountered issues."
    fi
    if [[ -x "$SCRIPT_DIR/test_gateway_end_to_end.sh" ]]; then
      if ! "$SCRIPT_DIR/test_gateway_end_to_end.sh" --endpoint "$GATEWAY_ENDPOINT" --environment "$ENVIRONMENT"; then
        warn "Gateway end-to-end tests reported failures."
      fi
    fi
  else
    warn "Skipping validation because gateway host could not be resolved."
  fi
else
  log "Validation skipped per flag."
fi

log "Gateway configuration snapshot saved to ${GATEWAY_SNAPSHOT}"
log "Summary recorded at ${SUMMARY_LOG}"
exit 0
