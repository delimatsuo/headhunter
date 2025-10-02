#!/usr/bin/env bash
set -euo pipefail


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# =============================================================================
# Infrastructure Notes Generator
# =============================================================================
# Queries all provisioned GCP resources and generates comprehensive documentation
#
# Usage:
#   ./generate-infrastructure-notes.sh --project-id PROJECT_ID [OPTIONS]
#
# Options:
#   --project-id ID      GCP project ID (required)
#   --config PATH        Config file path (default: config/infrastructure/headhunter-production.env)
#   --output-file PATH   Output file path (default: docs/infrastructure-notes.md)
#   --help               Show this help message
# =============================================================================

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
CONFIG_FILE="config/infrastructure/headhunter-production.env"
OUTPUT_FILE="docs/infrastructure-notes.md"
PROJECT_ID=""

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
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
        --output-file)
            OUTPUT_FILE="$2"
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

log_info "Generating infrastructure notes for project: $PROJECT_ID"

# =============================================================================
# Query GCP Resources
# =============================================================================

# Get project details
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)" 2>/dev/null || echo "unknown")
BILLING_ACCOUNT=$(gcloud billing projects describe "$PROJECT_ID" --format="value(billingAccountName)" 2>/dev/null || echo "unknown")

# Get network details
VPC_NAME="${VPC_NAME:-headhunter-vpc}"
VPC_CONNECTOR_NAME="${VPC_CONNECTOR_NAME:-headhunter-connector}"
REGION="${REGION:-us-central1}"

VPC_EXISTS=$(gcloud compute networks describe "$VPC_NAME" --project="$PROJECT_ID" --format=json 2>/dev/null || echo "{}")
VPC_CONNECTOR_EXISTS=$(gcloud compute networks vpc-access connectors describe "$VPC_CONNECTOR_NAME" --region="$REGION" --project="$PROJECT_ID" --format=json 2>/dev/null || echo "{}")

# Get Cloud SQL details
DB_INSTANCE_NAME="${DB_INSTANCE_NAME:-headhunter-db-primary}"
DB_CONNECTION_NAME=$(gcloud sql instances describe "$DB_INSTANCE_NAME" --project="$PROJECT_ID" --format="value(connectionName)" 2>/dev/null || echo "not-found")
DB_IP=$(gcloud sql instances describe "$DB_INSTANCE_NAME" --project="$PROJECT_ID" --format="value(ipAddresses[0].ipAddress)" 2>/dev/null || echo "not-found")
DB_VERSION=$(gcloud sql instances describe "$DB_INSTANCE_NAME" --project="$PROJECT_ID" --format="value(databaseVersion)" 2>/dev/null || echo "not-found")

# Get Redis details
REDIS_INSTANCE_NAME="${REDIS_INSTANCE_NAME:-headhunter-redis}"
REDIS_HOST=$(gcloud redis instances describe "$REDIS_INSTANCE_NAME" --region="$REGION" --project="$PROJECT_ID" --format="value(host)" 2>/dev/null || echo "not-found")
REDIS_PORT=$(gcloud redis instances describe "$REDIS_INSTANCE_NAME" --region="$REGION" --project="$PROJECT_ID" --format="value(port)" 2>/dev/null || echo "not-found")
REDIS_VERSION=$(gcloud redis instances describe "$REDIS_INSTANCE_NAME" --region="$REGION" --project="$PROJECT_ID" --format="value(redisVersion)" 2>/dev/null || echo "not-found")

# Get Pub/Sub topics and subscriptions
PUBSUB_TOPICS=$(gcloud pubsub topics list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null | sed 's|projects/.*/topics/||' || echo "")
PUBSUB_SUBSCRIPTIONS=$(gcloud pubsub subscriptions list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null | sed 's|projects/.*/subscriptions/||' || echo "")

# Get storage buckets
BUCKETS=$(gsutil ls -p "$PROJECT_ID" 2>/dev/null | sed 's|gs://||' | sed 's|/||' || echo "")

# Get secrets
SECRETS=$(gcloud secrets list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null || echo "")

# Get Firestore info
FIRESTORE_LOCATION=$(gcloud firestore databases describe --database="(default)" --project="$PROJECT_ID" --format="value(locationId)" 2>/dev/null || echo "not-found")

# Get service accounts
SERVICE_ACCOUNTS=$(gcloud iam service-accounts list --project="$PROJECT_ID" --format="table(email,displayName)" 2>/dev/null || echo "")

# =============================================================================
# Generate Markdown Document
# =============================================================================

log_info "Writing infrastructure notes to: $OUTPUT_FILE"

mkdir -p "$(dirname "$OUTPUT_FILE")"

cat > "$OUTPUT_FILE" <<'EOF'
# Headhunter Infrastructure Notes

> **Auto-generated infrastructure documentation**
> This file is generated by `scripts/generate-infrastructure-notes.sh`
> Last updated: TIMESTAMP_PLACEHOLDER

## Overview

This document contains details about all provisioned GCP resources for the Headhunter platform.

EOF

# Replace timestamp
sed -i.bak "s|TIMESTAMP_PLACEHOLDER|$(date -u '+%Y-%m-%d %H:%M:%S UTC')|" "$OUTPUT_FILE" && rm "${OUTPUT_FILE}.bak"

cat >> "$OUTPUT_FILE" <<EOF

### Project Information

- **Project ID**: \`$PROJECT_ID\`
- **Project Number**: \`$PROJECT_NUMBER\`
- **Primary Region**: \`$REGION\`
- **Billing Account**: \`$BILLING_ACCOUNT\`

---

## Network Configuration

### VPC Network

- **VPC Name**: \`$VPC_NAME\`
- **Subnet**: \`${SUBNET_NAME:-headhunter-subnet}\`
- **Subnet Range**: \`${SUBNET_CIDR:-10.0.0.0/24}\`

EOF

if [[ "$VPC_EXISTS" != "{}" ]]; then
    cat >> "$OUTPUT_FILE" <<EOF

**VPC Details:**
\`\`\`json
$(echo "$VPC_EXISTS" | jq '.' 2>/dev/null || echo "$VPC_EXISTS")
\`\`\`

EOF
fi

cat >> "$OUTPUT_FILE" <<EOF

### VPC Connector

- **Connector Name**: \`$VPC_CONNECTOR_NAME\`
- **Region**: \`$REGION\`

EOF

if [[ "$VPC_CONNECTOR_EXISTS" != "{}" ]]; then
    CONNECTOR_URI=$(echo "$VPC_CONNECTOR_EXISTS" | jq -r '.name // "not-available"' 2>/dev/null)
    cat >> "$OUTPUT_FILE" <<EOF

**Connector URI**: \`$CONNECTOR_URI\`

**Usage in Cloud Run:**
\`\`\`bash
gcloud run deploy SERVICE_NAME \\
  --vpc-connector=$VPC_CONNECTOR_NAME \\
  --vpc-egress=private-ranges-only \\
  --region=$REGION
\`\`\`

EOF
fi

cat >> "$OUTPUT_FILE" <<EOF

---

## Database Resources

### Cloud SQL (PostgreSQL + pgvector)

- **Instance Name**: \`$DB_INSTANCE_NAME\`
- **Connection Name**: \`$DB_CONNECTION_NAME\`
- **Private IP**: \`$DB_IP\`
- **Database Version**: \`$DB_VERSION\`
- **Region**: \`$REGION\`

**Connection String (Cloud Run):**
\`\`\`bash
postgres://USER:PASSWORD@$DB_IP:5432/DATABASE_NAME
\`\`\`

**Cloud SQL Proxy Connection (Local Development):**
\`\`\`bash
# Start Cloud SQL Proxy
cloud_sql_proxy -instances=$DB_CONNECTION_NAME=tcp:5432

# Connect via psql
psql "host=127.0.0.1 port=5432 dbname=headhunter user=headhunter_app"
\`\`\`

**Environment Variables for Cloud Run:**
\`\`\`bash
DB_HOST=$DB_IP
DB_PORT=5432
DB_NAME=headhunter
DB_USER=headhunter_app
# DB_PASSWORD from Secret Manager: db-primary-password
\`\`\`

---

## Cache Layer

### Redis (Memorystore)

- **Instance Name**: \`$REDIS_INSTANCE_NAME\`
- **Host**: \`$REDIS_HOST\`
- **Port**: \`$REDIS_PORT\`
- **Version**: \`$REDIS_VERSION\`
- **Region**: \`$REGION\`

**Connection URI:**
\`\`\`
redis://$REDIS_HOST:$REDIS_PORT
\`\`\`

**Environment Variables for Cloud Run:**
\`\`\`bash
REDIS_HOST=$REDIS_HOST
REDIS_PORT=$REDIS_PORT
\`\`\`

**Note**: Redis is only accessible via VPC. Cloud Run services must use the VPC connector.

---

## Message Queue

### Pub/Sub Topics

EOF

if [[ -n "$PUBSUB_TOPICS" ]]; then
    echo "$PUBSUB_TOPICS" | while read -r topic; do
        cat >> "$OUTPUT_FILE" <<EOF
- \`$topic\`
EOF
    done
else
    echo "- (No topics found)" >> "$OUTPUT_FILE"
fi

cat >> "$OUTPUT_FILE" <<EOF

### Pub/Sub Subscriptions

EOF

if [[ -n "$PUBSUB_SUBSCRIPTIONS" ]]; then
    echo "$PUBSUB_SUBSCRIPTIONS" | while read -r sub; do
        cat >> "$OUTPUT_FILE" <<EOF
- \`$sub\`
EOF
    done
else
    echo "- (No subscriptions found)" >> "$OUTPUT_FILE"
fi

cat >> "$OUTPUT_FILE" <<EOF

**Publishing to a Topic:**
\`\`\`bash
gcloud pubsub topics publish TOPIC_NAME --message="MESSAGE_CONTENT"
\`\`\`

---

## Storage

### Cloud Storage Buckets

EOF

if [[ -n "$BUCKETS" ]]; then
    echo "$BUCKETS" | while read -r bucket; do
        PURPOSE=""
        if [[ "$bucket" =~ "resumes" ]]; then
            PURPOSE=" (Resume uploads)"
        elif [[ "$bucket" =~ "exports" ]]; then
            PURPOSE=" (Data exports)"
        fi
        cat >> "$OUTPUT_FILE" <<EOF
- \`gs://$bucket\`$PURPOSE
EOF
    done
else
    echo "- (No buckets found)" >> "$OUTPUT_FILE"
fi

cat >> "$OUTPUT_FILE" <<EOF

**Uploading to a bucket:**
\`\`\`bash
gsutil cp LOCAL_FILE gs://BUCKET_NAME/path/to/file
\`\`\`

---

## Secrets

### Secret Manager

EOF

if [[ -n "$SECRETS" ]]; then
    echo "$SECRETS" | while read -r secret; do
        cat >> "$OUTPUT_FILE" <<EOF
- \`$secret\`
EOF
    done
else
    echo "- (No secrets found)" >> "$OUTPUT_FILE"
fi

cat >> "$OUTPUT_FILE" <<EOF

**Accessing a secret:**
\`\`\`bash
gcloud secrets versions access latest --secret=SECRET_NAME --project=$PROJECT_ID
\`\`\`

**Updating a secret:**
\`\`\`bash
echo -n "NEW_SECRET_VALUE" | gcloud secrets versions add SECRET_NAME --data-file=-
\`\`\`

**Environment Variables from Secrets (Cloud Run):**
\`\`\`bash
gcloud run deploy SERVICE_NAME \\
  --set-secrets=DB_PASSWORD=db-primary-password:latest,\\
TOGETHER_API_KEY=together-api-key:latest
\`\`\`

---

## Firestore

- **Database**: \`(default)\`
- **Location**: \`$FIRESTORE_LOCATION\`
- **Mode**: \`FIRESTORE_NATIVE\`

**Firestore Connection (Cloud Run):**

Cloud Run services automatically have access to Firestore via Application Default Credentials.

\`\`\`typescript
import { Firestore } from '@google-cloud/firestore';
const firestore = new Firestore({
  projectId: '$PROJECT_ID'
});
\`\`\`

---

## Service Accounts

EOF

if [[ -n "$SERVICE_ACCOUNTS" ]]; then
    cat >> "$OUTPUT_FILE" <<EOF
\`\`\`
$SERVICE_ACCOUNTS
\`\`\`

EOF
else
    echo "(No service accounts found)" >> "$OUTPUT_FILE"
fi

cat >> "$OUTPUT_FILE" <<EOF

---

## Connection Strings & Environment Variables

### Complete .env Template for Cloud Run Services

\`\`\`bash
# Project
PROJECT_ID=$PROJECT_ID
REGION=$REGION

# Database
DB_HOST=$DB_IP
DB_PORT=5432
DB_NAME=headhunter
DB_USER=headhunter_app
# DB_PASSWORD=<from Secret Manager: db-primary-password>

# Redis
REDIS_HOST=$REDIS_HOST
REDIS_PORT=$REDIS_PORT

# Together AI
# TOGETHER_API_KEY=<from Secret Manager: together-api-key>

# Gemini (optional)
# GEMINI_API_KEY=<from Secret Manager: gemini-api-key>
\`\`\`

---

## Next Steps

### 1. Populate Secrets with Real Values

The infrastructure provisioning creates placeholder secrets. You need to populate them with actual values:

\`\`\`bash
# Database password
echo -n "YOUR_SECURE_PASSWORD" | gcloud secrets versions add db-primary-password --data-file=-

# Together AI API key
echo -n "YOUR_TOGETHER_API_KEY" | gcloud secrets versions add together-api-key --data-file=-

# Gemini API key (optional)
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets versions add gemini-api-key --data-file=-
\`\`\`

### 2. Deploy Cloud Run Services

Follow the deployment guides:
- Evidence Service: \`docs/deployment/evidence-service.md\`
- ECO Service: \`docs/deployment/eco-service.md\`
- Admin Service: \`docs/deployment/admin-service.md\`
- Enrich Service: \`docs/deployment/enrich-service.md\`
- Messages Service: \`docs/deployment/msgs-service.md\`
- Search Service: \`docs/deployment/search-service.md\`

### 3. Configure API Gateway

Setup the API Gateway to route requests to Cloud Run services:
\`\`\`bash
./scripts/deploy_api_gateway.sh --project-id=$PROJECT_ID
\`\`\`

### 4. Run Post-Deployment Validation

\`\`\`bash
./scripts/validate_headhunter_infrastructure.sh --project-id=$PROJECT_ID
\`\`\`

### 5. Configure Monitoring & Alerting

Setup Cloud Monitoring dashboards and alerting:
\`\`\`bash
./scripts/setup_cloud_monitoring_dashboards.py --project-id=$PROJECT_ID
./scripts/setup_production_alerting.py --project-id=$PROJECT_ID
\`\`\`

---

## Validation Results

EOF

# Append validation results if available
log_info "Running infrastructure validation..."
if bash scripts/validate_headhunter_infrastructure.sh --project-id "$PROJECT_ID" --config "$CONFIG_FILE" 2>&1 | tee -a "$OUTPUT_FILE" >/dev/null; then
    log_success "Validation complete"
else
    log_warning "Validation encountered issues (this is normal if services aren't deployed yet)"
fi

cat >> "$OUTPUT_FILE" <<EOF

---

## Manual Notes

<!-- Add custom notes, troubleshooting info, or configuration details here -->
<!-- This section will not be overwritten when regenerating infrastructure notes -->

EOF

log_success "Infrastructure notes generated: $OUTPUT_FILE"
exit 0
