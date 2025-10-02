#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# =============================================================================
# GCP Infrastructure Cleanup Script
# =============================================================================
# Safely tears down provisioned GCP infrastructure in reverse order
#
# ⚠️  WARNING: This will DELETE resources and DATA. Use with caution!
#
# Usage:
#   ./cleanup-gcp-infrastructure.sh --project-id PROJECT_ID --confirm [OPTIONS]
#
# Options:
#   --project-id ID          GCP project ID (required)
#   --config PATH            Config file path (default: config/infrastructure/headhunter-production.env)
#   --confirm                Confirm you want to proceed (required)
#   --force-production       Allow cleanup of production project (headhunter-ai-0088)
#   --dry-run                Show what would be deleted without deleting
#   --only-storage           Only delete Cloud Storage buckets
#   --only-compute           Only delete compute resources (VPC, connectors)
#   --only-data              Only delete data resources (Cloud SQL, Redis, Firestore)
#   --keep-secrets           Preserve Secret Manager secrets
#   --disable-apis           Also disable APIs (default: keep enabled)
#   --help                   Show this help message
# =============================================================================

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
CONFIG_FILE="config/infrastructure/headhunter-production.env"
PROJECT_ID=""
CONFIRM=false
FORCE_PRODUCTION=false
DRY_RUN=false
ONLY_STORAGE=false
ONLY_COMPUTE=false
ONLY_DATA=false
KEEP_SECRETS=false
DISABLE_APIS=false
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE=".infrastructure/cleanup-${TIMESTAMP}.log"

# Deletion counters
DELETED_COUNT=0
FAILED_COUNT=0

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

show_usage() {
    grep "^#" "$0" | grep -v "#!/usr/bin/env bash" | sed 's/^# //' | sed 's/^#//'
}

delete_resource() {
    local resource_type=$1
    local resource_name=$2
    shift 2
    local delete_command="$@"

    log_info "Deleting $resource_type: $resource_name"

    if [[ "$DRY_RUN" == true ]]; then
        log_warning "[DRY RUN] Would execute: $delete_command"
        return 0
    fi

    if eval "$delete_command" >> "$LOG_FILE" 2>&1; then
        log_success "Deleted: $resource_name"
        ((DELETED_COUNT++))
        return 0
    else
        log_warning "Failed to delete: $resource_name (may not exist)"
        ((FAILED_COUNT++))
        return 1
    fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --project-id)
            PROJECT_ID="$2"
            shift 2
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --confirm)
            CONFIRM=true
            shift
            ;;
        --force-production)
            FORCE_PRODUCTION=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --only-storage)
            ONLY_STORAGE=true
            shift
            ;;
        --only-compute)
            ONLY_COMPUTE=true
            shift
            ;;
        --only-data)
            ONLY_DATA=true
            shift
            ;;
        --keep-secrets)
            KEEP_SECRETS=true
            shift
            ;;
        --disable-apis)
            DISABLE_APIS=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# =============================================================================
# Safety Checks
# =============================================================================

if [[ -z "$PROJECT_ID" ]]; then
    log_error "Missing required argument: --project-id"
    show_usage
    exit 1
fi

if [[ "$CONFIRM" != true ]]; then
    log_error "Missing required flag: --confirm"
    log_error "This is a destructive operation. You must explicitly confirm."
    exit 1
fi

# Production safety check
if [[ "$PROJECT_ID" == "headhunter-ai-0088" && "$FORCE_PRODUCTION" != true ]]; then
    log_error "Refusing to cleanup production project without --force-production flag"
    log_error "Project: $PROJECT_ID"
    exit 1
fi

# Confirmation prompt
log_warning "========================================="
log_warning "⚠️  DESTRUCTIVE OPERATION WARNING"
log_warning "========================================="
log_warning "This will DELETE infrastructure resources in project: $PROJECT_ID"
log_warning "This operation CANNOT be undone!"
log_warning "Data loss WILL occur!"
echo ""
read -p "Type the project ID '$PROJECT_ID' to confirm: " confirmation

if [[ "$confirmation" != "$PROJECT_ID" ]]; then
    log_error "Confirmation failed. Aborting."
    exit 1
fi

# Setup logging
mkdir -p .infrastructure
log_info "Cleanup log: $LOG_FILE"

# Load configuration
if [[ -f "$CONFIG_FILE" ]]; then
    log_info "Loading configuration from: $CONFIG_FILE"
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
else
    log_warning "Config file not found: $CONFIG_FILE. Using defaults."
fi

REGION="${REGION:-us-central1}"

# =============================================================================
# Cleanup Operations (in reverse order of provisioning)
# =============================================================================

log_info "========================================="
log_info "Starting Infrastructure Cleanup"
log_info "Project: $PROJECT_ID"
if [[ "$DRY_RUN" == true ]]; then
    log_warning "DRY RUN MODE - No changes will be made"
fi
log_info "========================================="
echo ""

# Step 1: Delete Cloud Storage Buckets
if [[ "$ONLY_STORAGE" == true || ("$ONLY_COMPUTE" == false && "$ONLY_DATA" == false) ]]; then
    log_info "Step 1: Deleting Cloud Storage buckets..."

    BUCKETS=$(gsutil ls -p "$PROJECT_ID" 2>/dev/null | sed 's|gs://||' | sed 's|/||' || echo "")

    if [[ -n "$BUCKETS" ]]; then
        echo "$BUCKETS" | while read -r bucket; do
            delete_resource "Cloud Storage Bucket" "$bucket" \
                "gsutil -m rm -r gs://${bucket}"
        done
    else
        log_info "No buckets found to delete"
    fi
    echo ""
fi

# Step 2: Delete Pub/Sub Resources
if [[ "$ONLY_DATA" == false && "$ONLY_COMPUTE" == false && "$ONLY_STORAGE" == false ]]; then
    log_info "Step 2: Deleting Pub/Sub subscriptions..."

    SUBSCRIPTIONS=$(gcloud pubsub subscriptions list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null || echo "")

    if [[ -n "$SUBSCRIPTIONS" ]]; then
        echo "$SUBSCRIPTIONS" | while read -r sub; do
            delete_resource "Pub/Sub Subscription" "$sub" \
                "gcloud pubsub subscriptions delete $sub --project=$PROJECT_ID --quiet"
        done
    else
        log_info "No subscriptions found to delete"
    fi

    log_info "Deleting Pub/Sub topics..."

    TOPICS=$(gcloud pubsub topics list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null || echo "")

    if [[ -n "$TOPICS" ]]; then
        echo "$TOPICS" | while read -r topic; do
            delete_resource "Pub/Sub Topic" "$topic" \
                "gcloud pubsub topics delete $topic --project=$PROJECT_ID --quiet"
        done
    else
        log_info "No topics found to delete"
    fi
    echo ""
fi

# Step 3: Delete Redis
if [[ "$ONLY_DATA" == true || ("$ONLY_COMPUTE" == false && "$ONLY_STORAGE" == false) ]]; then
    log_info "Step 3: Deleting Redis instance..."

    REDIS_INSTANCE_NAME="${REDIS_INSTANCE_NAME:-headhunter-redis}"

    delete_resource "Redis Instance" "$REDIS_INSTANCE_NAME" \
        "gcloud redis instances delete $REDIS_INSTANCE_NAME --region=$REGION --project=$PROJECT_ID --quiet"
    echo ""
fi

# Step 4: Delete Cloud SQL
if [[ "$ONLY_DATA" == true || ("$ONLY_COMPUTE" == false && "$ONLY_STORAGE" == false) ]]; then
    log_info "Step 4: Deleting Cloud SQL instance..."

    DB_INSTANCE_NAME="${DB_INSTANCE_NAME:-headhunter-db-primary}"

    log_warning "Cloud SQL deletion creates automatic backups for 7 days"

    delete_resource "Cloud SQL Instance" "$DB_INSTANCE_NAME" \
        "gcloud sql instances delete $DB_INSTANCE_NAME --project=$PROJECT_ID --quiet"
    echo ""
fi

# Step 5: Delete VPC Connector
if [[ "$ONLY_COMPUTE" == true || ("$ONLY_DATA" == false && "$ONLY_STORAGE" == false) ]]; then
    log_info "Step 5: Deleting VPC connector..."

    VPC_CONNECTOR_NAME="${VPC_CONNECTOR_NAME:-headhunter-connector}"

    delete_resource "VPC Connector" "$VPC_CONNECTOR_NAME" \
        "gcloud compute networks vpc-access connectors delete $VPC_CONNECTOR_NAME --region=$REGION --project=$PROJECT_ID --quiet"
    echo ""

    log_info "Step 6: Deleting NAT gateway and Cloud Router..."

    NAT_NAME="${NAT_NAME:-headhunter-nat}"
    ROUTER_NAME="${ROUTER_NAME:-headhunter-router}"

    delete_resource "NAT Gateway" "$NAT_NAME" \
        "gcloud compute routers nats delete $NAT_NAME --router=$ROUTER_NAME --region=$REGION --project=$PROJECT_ID --quiet"

    delete_resource "Cloud Router" "$ROUTER_NAME" \
        "gcloud compute routers delete $ROUTER_NAME --region=$REGION --project=$PROJECT_ID --quiet"
    echo ""

    log_info "Step 7: Deleting firewall rules..."

    FIREWALL_RULES=$(gcloud compute firewall-rules list --project="$PROJECT_ID" --format="value(name)" --filter="network:${VPC_NAME:-headhunter-vpc}" 2>/dev/null || echo "")

    if [[ -n "$FIREWALL_RULES" ]]; then
        echo "$FIREWALL_RULES" | while read -r rule; do
            delete_resource "Firewall Rule" "$rule" \
                "gcloud compute firewall-rules delete $rule --project=$PROJECT_ID --quiet"
        done
    else
        log_info "No firewall rules found to delete"
    fi
    echo ""

    log_info "Step 8: Deleting VPC subnets..."

    SUBNET_NAME="${SUBNET_NAME:-headhunter-subnet}"

    delete_resource "VPC Subnet" "$SUBNET_NAME" \
        "gcloud compute networks subnets delete $SUBNET_NAME --region=$REGION --project=$PROJECT_ID --quiet"
    echo ""

    log_info "Step 9: Deleting VPC network..."

    VPC_NAME="${VPC_NAME:-headhunter-vpc}"

    delete_resource "VPC Network" "$VPC_NAME" \
        "gcloud compute networks delete $VPC_NAME --project=$PROJECT_ID --quiet"
    echo ""
fi

# Step 10: Delete Secrets
if [[ "$KEEP_SECRETS" == false && "$ONLY_COMPUTE" == false && "$ONLY_DATA" == false && "$ONLY_STORAGE" == false ]]; then
    log_info "Step 10: Deleting Secret Manager secrets..."

    SECRETS=$(gcloud secrets list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null || echo "")

    if [[ -n "$SECRETS" ]]; then
        echo "$SECRETS" | while read -r secret; do
            delete_resource "Secret" "$secret" \
                "gcloud secrets delete $secret --project=$PROJECT_ID --quiet"
        done
    else
        log_info "No secrets found to delete"
    fi
    echo ""
else
    log_info "Step 10: Keeping Secret Manager secrets (--keep-secrets flag)"
    echo ""
fi

# Step 11: Delete Service Accounts
if [[ "$ONLY_COMPUTE" == false && "$ONLY_DATA" == false && "$ONLY_STORAGE" == false ]]; then
    log_info "Step 11: Deleting service accounts..."

    SERVICE_ACCOUNTS=$(gcloud iam service-accounts list --project="$PROJECT_ID" --format="value(email)" --filter="email:svc-*" 2>/dev/null || echo "")

    if [[ -n "$SERVICE_ACCOUNTS" ]]; then
        echo "$SERVICE_ACCOUNTS" | while read -r sa; do
            delete_resource "Service Account" "$sa" \
                "gcloud iam service-accounts delete $sa --project=$PROJECT_ID --quiet"
        done
    else
        log_info "No service accounts found to delete"
    fi
    echo ""
fi

# Step 12: Disable APIs (optional)
if [[ "$DISABLE_APIS" == true && "$ONLY_COMPUTE" == false && "$ONLY_DATA" == false && "$ONLY_STORAGE" == false ]]; then
    log_warning "Step 12: Disabling APIs..."
    log_warning "Note: Some APIs cannot be disabled and will be skipped"

    # Only disable non-essential APIs
    APIS_TO_DISABLE=(
        "vpcaccess.googleapis.com"
        "redis.googleapis.com"
        "secretmanager.googleapis.com"
    )

    for api in "${APIS_TO_DISABLE[@]}"; do
        delete_resource "API" "$api" \
            "gcloud services disable $api --project=$PROJECT_ID --quiet"
    done
    echo ""
else
    log_info "Step 12: Keeping APIs enabled"
    echo ""
fi

# =============================================================================
# Summary
# =============================================================================

log_info "========================================="
log_info "Cleanup Complete"
log_info "========================================="
echo ""

log_info "Cleanup Summary:"
log_info "  Resources deleted: $DELETED_COUNT"
log_info "  Resources failed: $FAILED_COUNT"
log_info "  Log file: $LOG_FILE"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    log_warning "DRY RUN MODE - No actual changes were made"
fi

if [[ $FAILED_COUNT -gt 0 ]]; then
    log_warning "Some resources could not be deleted (may not exist)"
    log_warning "Review the log file for details: $LOG_FILE"
fi

log_info "Verification:"
log_info "  gcloud sql instances list --project=$PROJECT_ID"
log_info "  gcloud redis instances list --region=$REGION --project=$PROJECT_ID"
log_info "  gcloud compute networks list --project=$PROJECT_ID"
log_info "  gsutil ls -p $PROJECT_ID"
echo ""

log_success "✅ Cleanup completed successfully!"
exit 0
