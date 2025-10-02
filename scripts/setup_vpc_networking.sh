#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

CONFIG_FILE="config/infrastructure/headhunter-production.env"
CLI_PROJECT_ID=""
REGION="us-central1"

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--project-id PROJECT_ID] [--config PATH]

Sets up VPC networking (vpc-hh, subnets, connector, NAT) for the headhunter platform.
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
  echo "Project ID must be provided via --project-id or config" >&2
  exit 1
fi

if [[ -z "${VPC_NAME:-}" || -z "${VPC_CONNECTOR:-}" ]]; then
  echo "VPC_NAME and VPC_CONNECTOR must be set in the config" >&2
  exit 1
fi

RUN_SUBNET_RANGE=${RUN_SUBNET_RANGE:-10.20.0.0/24}
SQL_SUBNET_RANGE=${SQL_SUBNET_RANGE:-10.20.1.0/24}
REDIS_SUBNET_RANGE=${REDIS_SUBNET_RANGE:-10.20.2.0/24}
CONNECTOR_RANGE=${CONNECTOR_RANGE:-10.20.10.0/28}
INTERNAL_SOURCE_RANGE=${INTERNAL_SOURCE_RANGE:-10.20.0.0/16}
CONNECTOR_EGRESS_ALLOWED_CIDRS=${CONNECTOR_EGRESS_ALLOWED_CIDRS:-0.0.0.0/0}

ROUTER_NAME=${ROUTER_NAME:-${VPC_NAME}-router}
NAT_GATEWAY_NAME=${NAT_GATEWAY_NAME:-${VPC_NAME}-nat}

log() {
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >&2
}

log "Setting project to ${PROJECT_ID}"
gcloud config set project "$PROJECT_ID" >/dev/null

log "Creating VPC ${VPC_NAME}"
if ! gcloud compute networks describe "$VPC_NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute networks create "$VPC_NAME" \
    --project="$PROJECT_ID" \
    --subnet-mode=custom
fi

create_subnet() {
  local name=$1
  local range=$2
  gcloud compute networks subnets describe "$name" --region="$REGION" \
    --project="$PROJECT_ID" >/dev/null 2>&1 && return 0

  gcloud compute networks subnets create "$name" \
    --project="$PROJECT_ID" \
    --network="$VPC_NAME" \
    --region="$REGION" \
    --range="$range" \
    --enable-private-ip-google-access
}

log "Ensuring subnets exist"
create_subnet "${VPC_SUBNET_RUN}" "$RUN_SUBNET_RANGE"
create_subnet "${VPC_SUBNET_SQL}" "$SQL_SUBNET_RANGE"
create_subnet "${VPC_SUBNET_REDIS}" "$REDIS_SUBNET_RANGE"

log "Configuring internal ingress firewall rules"
if gcloud compute firewall-rules describe hh-allow-internal --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute firewall-rules update hh-allow-internal \
    --project="$PROJECT_ID" \
    --allow=tcp:5432,tcp:6379,icmp \
    --source-ranges="$INTERNAL_SOURCE_RANGE" \
    --priority=65000
else
  gcloud compute firewall-rules create hh-allow-internal \
    --project="$PROJECT_ID" \
    --network="$VPC_NAME" \
    --direction=INGRESS \
    --priority=65000 \
    --source-ranges="$INTERNAL_SOURCE_RANGE" \
    --allow=tcp:5432,tcp:6379,icmp
fi

DESTINATION_RANGES=${CONNECTOR_EGRESS_ALLOWED_CIDRS//[[:space:]]/}
if [[ "$DESTINATION_RANGES" == "0.0.0.0/0" ]]; then
  log "CONNECTOR_EGRESS_ALLOWED_CIDRS not set; defaulting to broad egress"
else
  log "Allowing connector egress to ${DESTINATION_RANGES}"
fi

if gcloud compute firewall-rules describe hh-egress-allow --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute firewall-rules update hh-egress-allow \
    --project="$PROJECT_ID" \
    --rules=tcp:443 \
    --destination-ranges="$DESTINATION_RANGES" \
    --priority=900 \
    --enable-logging
else
  gcloud compute firewall-rules create hh-egress-allow \
    --project="$PROJECT_ID" \
    --network="$VPC_NAME" \
    --direction=EGRESS \
    --priority=900 \
    --action=ALLOW \
    --rules=tcp:443 \
    --destination-ranges="$DESTINATION_RANGES" \
    --enable-logging
fi

if gcloud compute firewall-rules describe hh-egress-deny --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute firewall-rules update hh-egress-deny \
    --project="$PROJECT_ID" \
    --rules=all \
    --destination-ranges=0.0.0.0/0 \
    --priority=910 \
    --enable-logging
else
  gcloud compute firewall-rules create hh-egress-deny \
    --project="$PROJECT_ID" \
    --network="$VPC_NAME" \
    --direction=EGRESS \
    --priority=910 \
    --action=DENY \
    --rules=all \
    --destination-ranges=0.0.0.0/0 \
    --enable-logging
fi

log "Creating Cloud Router ${ROUTER_NAME}"
if ! gcloud compute routers describe "$ROUTER_NAME" --region="$REGION" \
  --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute routers create "$ROUTER_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --network="$VPC_NAME"
fi

log "Creating Cloud NAT ${NAT_GATEWAY_NAME}"
if ! gcloud compute routers nats describe "$NAT_GATEWAY_NAME" \
  --router="$ROUTER_NAME" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute routers nats create "$NAT_GATEWAY_NAME" \
    --project="$PROJECT_ID" \
    --router="$ROUTER_NAME" \
    --region="$REGION" \
    --nat-all-subnet-ip-ranges \
    --auto-allocate-nat-external-ips \
    --enable-logging
fi

log "Provisioning Serverless VPC Access connector ${VPC_CONNECTOR}"
if ! gcloud compute networks vpc-access connectors describe "$VPC_CONNECTOR" \
    --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud compute networks vpc-access connectors create "$VPC_CONNECTOR" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --network="$VPC_NAME" \
    --range="$CONNECTOR_RANGE" \
    --min-instances=2 \
    --max-instances=10 \
    --machine-type=e2-micro
else
  log "Connector ${VPC_CONNECTOR} already exists"
fi

log "Networking setup complete"
