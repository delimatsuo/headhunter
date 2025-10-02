#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# =============================================================================
# Firestore Database Setup for Headhunter Platform
# =============================================================================
# Provisions Firestore database in native mode with indexes and IAM bindings
#
# Usage:
#   ./setup_firestore_headhunter.sh --project-id PROJECT_ID [OPTIONS]
#
# Options:
#   --project-id ID    GCP project ID (required)
#   --config PATH      Config file path (default: config/infrastructure/headhunter-production.env)
#   --region REGION    GCP region (default: from config or us-central1)
#   --help             Show this help message
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
REGION=""

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_usage() {
    grep "^#" "$0" | grep -v "#!/usr/bin/env bash" | sed 's/^# //' | sed 's/^#//'
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
        --region)
            REGION="$2"
            shift 2
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

# Validate required arguments
if [[ -z "$PROJECT_ID" ]]; then
    log_error "Missing required argument: --project-id"
    show_usage
    exit 1
fi

# Load configuration
if [[ -f "$CONFIG_FILE" ]]; then
    log_info "Loading configuration from: $CONFIG_FILE"
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
else
    log_warning "Config file not found: $CONFIG_FILE. Using defaults."
fi

# Set region from config or argument
REGION="${REGION:-${REGION:-us-central1}}"

log_info "========================================="
log_info "Setting up Firestore Database"
log_info "Project: $PROJECT_ID"
log_info "Region: $REGION"
log_info "========================================="

# =============================================================================
# Step 1: Check if Firestore database exists
# =============================================================================

log_info "Checking for existing Firestore database..."

DB_EXISTS=$(gcloud firestore databases list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null | grep -c "(default)" || echo "0")

if [[ "$DB_EXISTS" != "0" ]]; then
    log_success "Firestore database already exists"
    DB_INFO=$(gcloud firestore databases describe --database="(default)" --project="$PROJECT_ID" --format="table(name,locationId,type)" 2>/dev/null || echo "")
    echo "$DB_INFO"
else
    log_info "Creating Firestore database in native mode..."

    # Create Firestore database
    if gcloud firestore databases create \
        --location="$REGION" \
        --type=firestore-native \
        --project="$PROJECT_ID" \
        --quiet; then
        log_success "Firestore database created successfully"
    else
        log_error "Failed to create Firestore database"
        log_error "This may be because:"
        log_error "  - A Datastore mode database already exists (cannot convert)"
        log_error "  - Insufficient permissions"
        log_error "  - Region not supported"
        exit 1
    fi
fi

# =============================================================================
# Step 2: Deploy Firestore indexes
# =============================================================================

log_info "Checking for Firestore indexes configuration..."

INDEX_FILE="firestore.indexes.json"

if [[ -f "$INDEX_FILE" ]]; then
    log_info "Deploying Firestore indexes from: $INDEX_FILE"

    # Check if indexes are already up-to-date
    CURRENT_INDEXES=$(gcloud firestore indexes composite list --database="(default)" --project="$PROJECT_ID" --format=json 2>/dev/null || echo "[]")

    if [[ "$CURRENT_INDEXES" == "[]" || "$CURRENT_INDEXES" == "" ]]; then
        log_info "No existing indexes found. Creating new indexes..."

        if gcloud firestore indexes create \
            --database="(default)" \
            --index-file="$INDEX_FILE" \
            --project="$PROJECT_ID" \
            --quiet 2>/dev/null; then
            log_success "Firestore indexes created successfully"
            log_info "Note: Index creation may take several minutes to complete"
        else
            log_warning "Failed to create some indexes (they may already exist)"
        fi
    else
        log_info "Existing indexes found. Checking for updates..."
        # gcloud firestore indexes create is idempotent and will skip existing indexes
        if gcloud firestore indexes create \
            --database="(default)" \
            --index-file="$INDEX_FILE" \
            --project="$PROJECT_ID" \
            --quiet 2>/dev/null; then
            log_success "Firestore indexes are up-to-date"
        else
            log_warning "Some index operations failed (they may already be up-to-date)"
        fi
    fi

    # Show current indexes
    log_info "Current Firestore indexes:"
    gcloud firestore indexes composite list \
        --database="(default)" \
        --project="$PROJECT_ID" \
        --format="table(name,state)" 2>/dev/null || log_warning "Could not list indexes"
else
    log_warning "Firestore indexes file not found: $INDEX_FILE"
    log_warning "Skipping index creation. You may need to create indexes manually."
fi

# =============================================================================
# Step 3: Configure IAM bindings for service accounts
# =============================================================================

log_info "Configuring IAM bindings for service accounts..."

# Define service accounts and their roles
# These should match the service accounts created in setup_service_iam.sh
declare -A SERVICE_ACCOUNTS=(
    ["${SVC_EVIDENCE:-svc-evidence@${PROJECT_ID}.iam.gserviceaccount.com}"]="roles/datastore.user"
    ["${SVC_ECO:-svc-eco@${PROJECT_ID}.iam.gserviceaccount.com}"]="roles/datastore.user"
    ["${SVC_ADMIN:-svc-admin@${PROJECT_ID}.iam.gserviceaccount.com}"]="roles/datastore.user"
    ["${SVC_ENRICH:-svc-enrich@${PROJECT_ID}.iam.gserviceaccount.com}"]="roles/datastore.user"
    ["${SVC_MSGS:-svc-msgs@${PROJECT_ID}.iam.gserviceaccount.com}"]="roles/datastore.user"
    ["${SVC_SEARCH:-svc-search@${PROJECT_ID}.iam.gserviceaccount.com}"]="roles/datastore.viewer"
)

for SA in "${!SERVICE_ACCOUNTS[@]}"; do
    ROLE="${SERVICE_ACCOUNTS[$SA]}"
    log_info "Granting $ROLE to $SA..."

    if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA" \
        --role="$ROLE" \
        --condition=None \
        --quiet 2>/dev/null; then
        log_success "Granted $ROLE to $SA"
    else
        log_warning "Failed to grant $ROLE to $SA (may already exist or service account not found)"
    fi
done

# =============================================================================
# Summary
# =============================================================================

log_info "========================================="
log_success "Firestore Setup Complete"
log_info "========================================="

log_info ""
log_info "Firestore Database Details:"
log_info "  Database: (default)"
log_info "  Location: $REGION"
log_info "  Type: FIRESTORE_NATIVE"
log_info "  Project: $PROJECT_ID"
log_info ""

# Capture database info for output
gcloud firestore databases describe \
    --database="(default)" \
    --project="$PROJECT_ID" \
    --format=json 2>/dev/null || log_warning "Could not retrieve database details"

log_info ""
log_info "Next steps:"
log_info "  1. Verify indexes are building: gcloud firestore indexes composite list --project=$PROJECT_ID"
log_info "  2. Test Firestore access from Cloud Run services"
log_info "  3. Configure Firestore security rules if needed"
log_info ""

log_success "✅ Firestore is ready for use!"
exit 0
