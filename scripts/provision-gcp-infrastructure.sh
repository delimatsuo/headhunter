#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# =============================================================================
# GCP Infrastructure Provisioning Orchestrator
# =============================================================================
# Master script to provision all Headhunter GCP infrastructure components
# with enhanced output capture, validation, and documentation generation.
#
# Usage:
#   ./provision-gcp-infrastructure.sh --project-id PROJECT_ID [OPTIONS]
#
# Options:
#   --project-id ID        GCP project ID (required)
#   --config PATH          Config file path (default: config/infrastructure/headhunter-production.env)
#   --output-dir PATH      Output directory for logs (default: .infrastructure/provision-TIMESTAMP)
#   --dry-run              Show what would be done without making changes
#   --skip-validation      Skip post-provisioning validation
#   --help                 Show this help message
# =============================================================================

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
CONFIG_FILE="config/infrastructure/headhunter-production.env"
DRY_RUN=false
SKIP_VALIDATION=false
PROJECT_ID=""
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_DIR=".infrastructure/provision-${TIMESTAMP}"

# =============================================================================
# Helper Functions
# =============================================================================

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

# =============================================================================
# Parse Arguments
# =============================================================================

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
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-validation)
            SKIP_VALIDATION=true
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
# Pre-flight Checks
# =============================================================================

log_info "Starting pre-flight checks..."

# Check required arguments
if [[ -z "$PROJECT_ID" ]]; then
    log_error "Missing required argument: --project-id"
    show_usage
    exit 1
fi

# Check gcloud installation
if ! command -v gcloud &> /dev/null; then
    log_error "gcloud CLI not found. Please install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check gcloud authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    log_error "No active gcloud authentication found. Please run: gcloud auth login"
    exit 1
fi

# Check user permissions
log_info "Verifying IAM permissions..."
CURRENT_USER=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
PROJECT_IAM=$(gcloud projects get-iam-policy "$PROJECT_ID" --flatten="bindings[].members" --format="table(bindings.role)" --filter="bindings.members:$CURRENT_USER" 2>/dev/null || echo "")

if [[ ! "$PROJECT_IAM" =~ (roles/owner|roles/editor) ]]; then
    log_warning "User $CURRENT_USER may not have sufficient permissions (Owner or Editor role) on project $PROJECT_ID"
    log_warning "Continuing anyway, but some operations may fail..."
fi

# Check config file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    log_error "Config file not found: $CONFIG_FILE"
    exit 1
fi

log_info "Loading configuration from: $CONFIG_FILE"
# shellcheck source=/dev/null
source "$CONFIG_FILE"

# Validate secret prerequisites
log_info "Validating secret prerequisites..."
if [[ -f "scripts/validate-secret-prerequisites.sh" ]]; then
if "${BASH:-bash}" scripts/validate-secret-prerequisites.sh --check-only; then
        log_success "All required secrets are available"
    else
        log_warning "Some secrets are missing. Infrastructure will be provisioned with placeholder secrets."
        log_warning "You will need to populate them manually after provisioning."
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Aborting provisioning."
            exit 0
        fi
    fi
else
    log_warning "Secret validation script not found. Skipping secret checks."
fi

# =============================================================================
# Setup Output Directory
# =============================================================================

log_info "Creating output directory: $OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
LOG_FILE="$OUTPUT_DIR/provision.log"

# Redirect all output to log file while still showing on screen
exec > >(tee -a "$LOG_FILE")
exec 2>&1

log_info "Provisioning logs will be saved to: $LOG_FILE"

# Save provisioning context
cat > "$OUTPUT_DIR/provision-context.json" <<EOF
{
  "timestamp": "$TIMESTAMP",
  "project_id": "$PROJECT_ID",
  "region": "${REGION:-us-central1}",
  "config_file": "$CONFIG_FILE",
  "user": "$CURRENT_USER",
  "dry_run": $DRY_RUN
}
EOF

# =============================================================================
# Dry Run Check
# =============================================================================

if [[ "$DRY_RUN" == true ]]; then
    log_warning "DRY RUN MODE - No changes will be made"
    log_info "Would provision infrastructure with the following configuration:"
    cat "$OUTPUT_DIR/provision-context.json"
    log_info "Would execute the following steps:"
    echo "  1. Enable required GCP APIs"
    echo "  2. Setup Secret Manager secrets"
    echo "  3. Provision VPC networking"
    echo "  4. Create Cloud SQL instance with pgvector"
    echo "  5. Create Redis instance"
    echo "  6. Setup Pub/Sub topics and subscriptions"
    echo "  7. Create Cloud Storage buckets"
    echo "  8. Setup Firestore database"
    echo "  9. Generate infrastructure notes"
    echo "  10. Run validation checks"
    exit 0
fi

# =============================================================================
# Provisioning Steps
# =============================================================================

log_info "========================================="
log_info "Starting GCP Infrastructure Provisioning"
log_info "Project: $PROJECT_ID"
log_info "Region: ${REGION:-us-central1}"
log_info "========================================="

# Track provisioning status
PROVISIONING_ERRORS=0

# Step 1: Enable Required APIs
log_info "Step 1/8: Enabling required GCP APIs..."
if "${BASH:-bash}" scripts/enable_required_apis.sh --project-id "$PROJECT_ID" > "$OUTPUT_DIR/01-apis.log" 2>&1; then
    log_success "APIs enabled successfully"
    gcloud services list --enabled --project="$PROJECT_ID" > "$OUTPUT_DIR/enabled-apis.txt"
else
    log_error "Failed to enable APIs. Check $OUTPUT_DIR/01-apis.log"
    ((PROVISIONING_ERRORS++))
fi

# Step 2: Setup Secret Manager
log_info "Step 2/8: Setting up Secret Manager..."
if "${BASH:-bash}" scripts/setup_secret_manager_headhunter.sh --project-id "$PROJECT_ID" --config "$CONFIG_FILE" > "$OUTPUT_DIR/02-secrets.log" 2>&1; then
    log_success "Secret Manager configured successfully"
    gcloud secrets list --project="$PROJECT_ID" --format="table(name,created)" > "$OUTPUT_DIR/secrets-list.txt"
else
    log_error "Failed to setup Secret Manager. Check $OUTPUT_DIR/02-secrets.log"
    ((PROVISIONING_ERRORS++))
fi

# Step 3: Setup VPC Networking
log_info "Step 3/8: Provisioning VPC networking..."
if "${BASH:-bash}" scripts/setup_vpc_networking.sh --project-id "$PROJECT_ID" --config "$CONFIG_FILE" > "$OUTPUT_DIR/03-networking.log" 2>&1; then
    log_success "VPC networking configured successfully"
    # Capture VPC details
    gcloud compute networks describe "${VPC_NAME:-headhunter-vpc}" --project="$PROJECT_ID" --format=json > "$OUTPUT_DIR/vpc-details.json" 2>/dev/null || true
    gcloud compute networks vpc-access connectors describe "${VPC_CONNECTOR_NAME:-headhunter-connector}" \
        --region="${REGION:-us-central1}" --project="$PROJECT_ID" --format=json > "$OUTPUT_DIR/vpc-connector-details.json" 2>/dev/null || true
else
    log_error "Failed to setup VPC networking. Check $OUTPUT_DIR/03-networking.log"
    ((PROVISIONING_ERRORS++))
fi

# Step 4: Setup Cloud SQL
log_info "Step 4/8: Creating Cloud SQL instance..."
if "${BASH:-bash}" scripts/setup_cloud_sql_headhunter.sh --project-id "$PROJECT_ID" --config "$CONFIG_FILE" > "$OUTPUT_DIR/04-cloud-sql.log" 2>&1; then
    log_success "Cloud SQL instance created successfully"
    # Capture Cloud SQL details
    gcloud sql instances describe "${DB_INSTANCE_NAME:-headhunter-db-primary}" --project="$PROJECT_ID" --format=json > "$OUTPUT_DIR/cloud-sql-details.json" 2>/dev/null || true
else
    log_error "Failed to create Cloud SQL instance. Check $OUTPUT_DIR/04-cloud-sql.log"
    ((PROVISIONING_ERRORS++))
fi

# Step 5: Setup Redis
log_info "Step 5/8: Creating Redis instance..."
if "${BASH:-bash}" scripts/setup_redis_headhunter.sh --project-id "$PROJECT_ID" --config "$CONFIG_FILE" > "$OUTPUT_DIR/05-redis.log" 2>&1; then
    log_success "Redis instance created successfully"
    # Capture Redis details
    gcloud redis instances describe "${REDIS_INSTANCE_NAME:-headhunter-redis}" \
        --region="${REGION:-us-central1}" --project="$PROJECT_ID" --format=json > "$OUTPUT_DIR/redis-details.json" 2>/dev/null || true
else
    log_error "Failed to create Redis instance. Check $OUTPUT_DIR/05-redis.log"
    ((PROVISIONING_ERRORS++))
fi

# Step 6: Setup Pub/Sub
log_info "Step 6/8: Setting up Pub/Sub topics and subscriptions..."
if "${BASH:-bash}" scripts/setup_pubsub_headhunter.sh --project-id "$PROJECT_ID" --config "$CONFIG_FILE" > "$OUTPUT_DIR/06-pubsub.log" 2>&1; then
    log_success "Pub/Sub configured successfully"
    # Capture Pub/Sub details
    gcloud pubsub topics list --project="$PROJECT_ID" --format="table(name)" > "$OUTPUT_DIR/pubsub-topics.txt"
    gcloud pubsub subscriptions list --project="$PROJECT_ID" --format="table(name,topic)" > "$OUTPUT_DIR/pubsub-subscriptions.txt"
else
    log_error "Failed to setup Pub/Sub. Check $OUTPUT_DIR/06-pubsub.log"
    ((PROVISIONING_ERRORS++))
fi

# Step 7: Setup Cloud Storage
log_info "Step 7/8: Creating Cloud Storage buckets..."
if "${BASH:-bash}" scripts/setup_cloud_storage_headhunter.sh --project-id "$PROJECT_ID" --config "$CONFIG_FILE" > "$OUTPUT_DIR/07-storage.log" 2>&1; then
    log_success "Cloud Storage buckets created successfully"
    # Capture bucket details
    gsutil ls -L -b "gs://${PROJECT_ID}-resumes" > "$OUTPUT_DIR/bucket-resumes.txt" 2>/dev/null || true
    gsutil ls -L -b "gs://${PROJECT_ID}-data-exports" > "$OUTPUT_DIR/bucket-exports.txt" 2>/dev/null || true
else
    log_error "Failed to create Cloud Storage buckets. Check $OUTPUT_DIR/07-storage.log"
    ((PROVISIONING_ERRORS++))
fi

# Step 8: Setup Firestore
log_info "Step 8/8: Setting up Firestore database..."
if [[ -f "scripts/setup_firestore_headhunter.sh" ]]; then
    if "${BASH:-bash}" scripts/setup_firestore_headhunter.sh --project-id "$PROJECT_ID" --config "$CONFIG_FILE" > "$OUTPUT_DIR/08-firestore.log" 2>&1; then
        log_success "Firestore database configured successfully"
        # Capture Firestore details
        gcloud firestore databases list --project="$PROJECT_ID" --format="table(name,location,type)" > "$OUTPUT_DIR/firestore-details.txt" 2>/dev/null || true
    else
        log_error "Failed to setup Firestore. Check $OUTPUT_DIR/08-firestore.log"
        ((PROVISIONING_ERRORS++))
    fi
else
    log_warning "Firestore setup script not found. Skipping Firestore provisioning."
fi

# =============================================================================
# Generate Infrastructure Notes
# =============================================================================

log_info "Generating infrastructure documentation..."
if [[ -f "scripts/generate-infrastructure-notes.sh" ]]; then
    if "${BASH:-bash}" scripts/generate-infrastructure-notes.sh --project-id "$PROJECT_ID" --config "$CONFIG_FILE" --output-file "docs/infrastructure-notes.md" > "$OUTPUT_DIR/infrastructure-notes.log" 2>&1; then
        log_success "Infrastructure notes generated: docs/infrastructure-notes.md"
        cp docs/infrastructure-notes.md "$OUTPUT_DIR/infrastructure-notes.md"
    else
        log_warning "Failed to generate infrastructure notes. Check $OUTPUT_DIR/infrastructure-notes.log"
    fi
else
    log_warning "Infrastructure notes generation script not found. Skipping documentation generation."
fi

# =============================================================================
# Validation
# =============================================================================

if [[ "$SKIP_VALIDATION" == false ]]; then
    log_info "Running infrastructure validation..."
    if "${BASH:-bash}" scripts/validate_headhunter_infrastructure.sh --project-id "$PROJECT_ID" --config "$CONFIG_FILE" > "$OUTPUT_DIR/validation.log" 2>&1; then
        log_success "Infrastructure validation passed"
    else
        log_warning "Infrastructure validation found issues. Check $OUTPUT_DIR/validation.log"
        ((PROVISIONING_ERRORS++))
    fi
else
    log_info "Skipping validation (--skip-validation flag provided)"
fi

# =============================================================================
# Summary
# =============================================================================

log_info "========================================="
log_info "Provisioning Complete!"
log_info "========================================="

if [[ $PROVISIONING_ERRORS -eq 0 ]]; then
    log_success "All infrastructure components provisioned successfully"
else
    log_warning "Provisioning completed with $PROVISIONING_ERRORS error(s)"
    log_warning "Review the logs in $OUTPUT_DIR for details"
fi

log_info ""
log_info "📋 Provisioning Summary:"
log_info "  Project ID: $PROJECT_ID"
log_info "  Region: ${REGION:-us-central1}"
log_info "  Output Directory: $OUTPUT_DIR"
log_info "  Infrastructure Notes: docs/infrastructure-notes.md"
log_info ""
log_info "📝 Next Steps:"
log_info "  1. Review the infrastructure notes: docs/infrastructure-notes.md"
log_info "  2. Populate secrets with real values (see docs/infrastructure-notes.md)"
log_info "  3. Deploy Cloud Run services (see deployment documentation)"
log_info "  4. Configure API Gateway (see gateway documentation)"
log_info "  5. Run end-to-end validation"
log_info ""

if [[ $PROVISIONING_ERRORS -gt 0 ]]; then
    log_warning "⚠️  Some steps failed. Review logs before proceeding."
    exit 1
else
    log_success "✅ Infrastructure is ready for service deployment!"
    exit 0
fi
