#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# =============================================================================
# Secret Prerequisites Validator
# =============================================================================
# Validates that required secret values are available before infrastructure provisioning
#
# Usage:
#   ./validate-secret-prerequisites.sh [OPTIONS]
#
# Options:
#   --strict         Exit with error if any required secret is missing
#   --check-only     Only report status without exiting
#   --generate-template  Generate .env.secrets.template file
#   --help           Show this help message
# =============================================================================

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Modes
STRICT_MODE=false
CHECK_ONLY=false
GENERATE_TEMPLATE=false

# Status counters
MISSING_REQUIRED=0
MISSING_OPTIONAL=0
WEAK_SECRETS=0

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
        --strict)
            STRICT_MODE=true
            shift
            ;;
        --check-only)
            CHECK_ONLY=true
            shift
            ;;
        --generate-template)
            GENERATE_TEMPLATE=true
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
# Secret Validation Functions
# =============================================================================

check_secret() {
    local var_name=$1
    local display_name=$2
    local required=$3
    local min_length=${4:-20}

    if [[ -z "${!var_name:-}" ]]; then
        if [[ "$required" == "true" ]]; then
            log_error "Missing required secret: $display_name (env var: $var_name)"
            ((MISSING_REQUIRED++))
        else
            log_warning "Missing optional secret: $display_name (env var: $var_name)"
            ((MISSING_OPTIONAL++))
        fi
        return 1
    fi

    # Check length
    local value="${!var_name}"
    if [[ ${#value} -lt $min_length ]]; then
        log_warning "Weak secret: $display_name is shorter than recommended ($min_length chars)"
        ((WEAK_SECRETS++))
    fi

    log_success "Found: $display_name ✓"
    return 0
}

check_json_secret() {
    local var_name=$1
    local display_name=$2
    local required=$3

    if [[ -z "${!var_name:-}" ]]; then
        if [[ "$required" == "true" ]]; then
            log_error "Missing required secret: $display_name (env var: $var_name)"
            ((MISSING_REQUIRED++))
        else
            log_warning "Missing optional secret: $display_name (env var: $var_name)"
            ((MISSING_OPTIONAL++))
        fi
        return 1
    fi

    # Validate JSON format
    if ! echo "${!var_name}" | jq . >/dev/null 2>&1; then
        log_error "Invalid JSON format: $display_name"
        ((MISSING_REQUIRED++))
        return 1
    fi

    log_success "Found: $display_name ✓ (valid JSON)"
    return 0
}

# =============================================================================
# Generate Template
# =============================================================================

if [[ "$GENERATE_TEMPLATE" == true ]]; then
    log_info "Generating secret template..."

    cat > .env.secrets.template <<'EOF'
# =============================================================================
# Headhunter Platform - Secrets Template
# =============================================================================
# Copy this file to .env.secrets and populate with actual values
# NEVER commit .env.secrets to version control!
# =============================================================================

# -----------------------------------------------------------------------------
# Database Passwords (Required)
# -----------------------------------------------------------------------------
# Generate secure passwords with: openssl rand -base64 32
# Minimum 20 characters recommended

# Primary database admin password
HH_SECRET_DB_PRIMARY_PASSWORD=""

# Replica database user password
HH_SECRET_DB_REPLICA_PASSWORD=""

# Analytics database user password (read-only)
HH_SECRET_DB_ANALYTICS_PASSWORD=""

# -----------------------------------------------------------------------------
# AI Service API Keys (Required)
# -----------------------------------------------------------------------------

# Together AI API key (required for production AI processing)
# Get from: https://api.together.xyz/settings/api-keys
HH_SECRET_TOGETHER_AI_API_KEY=""

# Google Gemini API key (optional, for fallback embedding provider)
# Get from: https://aistudio.google.com/app/apikey
HH_SECRET_GEMINI_API_KEY=""

# -----------------------------------------------------------------------------
# OAuth2 Configuration (Required)
# -----------------------------------------------------------------------------
# JSON object with client credentials
# Format: {"client_id": "...", "client_secret": "...", "redirect_uris": ["..."]}
HH_SECRET_OAUTH_CLIENT_CREDENTIALS='{}'

# -----------------------------------------------------------------------------
# Cloud Storage (Required)
# -----------------------------------------------------------------------------
# Storage signed URL signing key
# Generate with: openssl rand -base64 32
HH_SECRET_STORAGE_SIGNER_KEY=""

# -----------------------------------------------------------------------------
# Optional Secrets
# -----------------------------------------------------------------------------

# Custom encryption key (optional)
HH_SECRET_ENCRYPTION_KEY=""

# Webhook signing secret (optional)
HH_SECRET_WEBHOOK_SECRET=""

EOF

    log_success "Template generated: .env.secrets.template"
    log_info "Copy to .env.secrets and populate with actual values"
    exit 0
fi

# =============================================================================
# Run Validation
# =============================================================================

log_info "========================================="
log_info "Validating Secret Prerequisites"
log_info "========================================="
echo ""

log_info "Checking required secrets..."
echo ""

# Required database passwords
check_secret "HH_SECRET_DB_PRIMARY_PASSWORD" "Primary Database Password" true 20
check_secret "HH_SECRET_DB_REPLICA_PASSWORD" "Replica Database Password" true 20
check_secret "HH_SECRET_DB_ANALYTICS_PASSWORD" "Analytics Database Password" true 20

echo ""

# Required API keys
check_secret "HH_SECRET_TOGETHER_AI_API_KEY" "Together AI API Key" true 32
check_secret "HH_SECRET_STORAGE_SIGNER_KEY" "Storage Signer Key" true 20

echo ""

# Required OAuth credentials
check_json_secret "HH_SECRET_OAUTH_CLIENT_CREDENTIALS" "OAuth2 Client Credentials" true

echo ""

# Optional secrets
log_info "Checking optional secrets..."
echo ""

check_secret "HH_SECRET_GEMINI_API_KEY" "Gemini API Key" false 32
check_secret "HH_SECRET_ENCRYPTION_KEY" "Encryption Key" false 32
check_secret "HH_SECRET_WEBHOOK_SECRET" "Webhook Secret" false 32

# =============================================================================
# Summary
# =============================================================================

echo ""
log_info "========================================="
log_info "Validation Summary"
log_info "========================================="
echo ""

if [[ $MISSING_REQUIRED -eq 0 && $WEAK_SECRETS -eq 0 ]]; then
    log_success "✅ All required secrets are present and valid!"
    if [[ $MISSING_OPTIONAL -gt 0 ]]; then
        log_info "Optional secrets missing: $MISSING_OPTIONAL"
    fi
    exit 0
fi

if [[ $MISSING_REQUIRED -gt 0 ]]; then
    log_error "❌ Missing required secrets: $MISSING_REQUIRED"
fi

if [[ $WEAK_SECRETS -gt 0 ]]; then
    log_warning "⚠️  Weak secrets detected: $WEAK_SECRETS"
fi

if [[ $MISSING_OPTIONAL -gt 0 ]]; then
    log_info "ℹ️  Missing optional secrets: $MISSING_OPTIONAL"
fi

echo ""
log_info "========================================="
log_info "How to Fix"
log_info "========================================="
echo ""

if [[ $MISSING_REQUIRED -gt 0 ]]; then
    log_info "Generate secure passwords:"
    echo "  openssl rand -base64 32"
    echo ""

    log_info "Set environment variables:"
    echo "  export HH_SECRET_DB_PRIMARY_PASSWORD=\"<generated-password>\""
    echo "  export HH_SECRET_TOGETHER_AI_API_KEY=\"<your-api-key>\""
    echo ""

    log_info "Or create .env.secrets file:"
    echo "  1. Generate template: $0 --generate-template"
    echo "  2. Copy to .env.secrets"
    echo "  3. Populate with actual values"
    echo "  4. Source the file: source .env.secrets"
    echo ""
fi

if [[ $WEAK_SECRETS -gt 0 ]]; then
    log_info "Strengthen weak secrets:"
    echo "  Use at least 20 characters for passwords"
    echo "  Use at least 32 characters for API keys and signing keys"
    echo ""
fi

# Exit based on mode
if [[ "$STRICT_MODE" == true && $MISSING_REQUIRED -gt 0 ]]; then
    log_error "Strict mode: Exiting due to missing required secrets"
    exit 1
elif [[ "$CHECK_ONLY" == true ]]; then
    log_info "Check-only mode: Reporting status only"
    # Return non-zero if required secrets are missing even in check-only mode
    if [[ $MISSING_REQUIRED -gt 0 ]]; then
        exit 1
    else
        exit 0
    fi
else
    log_warning "Continuing with missing secrets (placeholder values will be used)"
    log_warning "You can populate them after infrastructure provisioning"
    exit 1
fi
