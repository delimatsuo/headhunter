#!/bin/bash

SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

#
# Infrastructure validation script for Headhunter AI
# Validates that all GCP resources are correctly configured
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
PROJECT_ID=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --project-id)
            PROJECT_ID="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --project-id PROJECT_ID"
            exit 1
            ;;
    esac
done

# Validate project ID
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT_ID" ]; then
        echo -e "${RED}❌ No project ID specified${NC}"
        echo "Usage: $0 --project-id PROJECT_ID"
        exit 1
    fi
fi

echo -e "${BLUE}🔍 Validating Infrastructure for Project: $PROJECT_ID${NC}"
echo "============================================================"

# Set project
gcloud config set project $PROJECT_ID >/dev/null 2>&1

# Track validation results
ERRORS=0
WARNINGS=0

# Function to check resource
check_resource() {
    local resource_type="$1"
    local resource_name="$2"
    local check_command="$3"

    echo -n -e "Checking $resource_type: $resource_name... "

    if eval "$check_command" >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${RED}✗${NC}"
        ((ERRORS++))
        return 1
    fi
}

# Function to check region
check_region() {
    local resource_type="$1"
    local expected_region="$2"
    local actual_region="$3"

    echo -n -e "  Region check... "

    if [[ "$actual_region" == *"$expected_region"* ]]; then
        echo -e "${GREEN}✓ $expected_region${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ $actual_region (expected $expected_region)${NC}"
        ((WARNINGS++))
        return 1
    fi
}

echo ""
echo -e "${YELLOW}1. Checking APIs...${NC}"
echo "-------------------"

REQUIRED_APIS=(
    "firestore.googleapis.com"
    "storage.googleapis.com"
    "cloudfunctions.googleapis.com"
    "firebase.googleapis.com"
    "run.googleapis.com"
    "secretmanager.googleapis.com"
    "aiplatform.googleapis.com"
)

for api in "${REQUIRED_APIS[@]}"; do
    check_resource "API" "$api" "gcloud services list --enabled --filter=\"config.name:$api\" --format=\"value(config.name)\" | grep -q \"$api\""
done

echo ""
echo -e "${YELLOW}2. Checking Service Accounts...${NC}"
echo "--------------------------------"

check_resource "Functions SA" "headhunter-functions-sa" "gcloud iam service-accounts describe headhunter-functions-sa@$PROJECT_ID.iam.gserviceaccount.com"
check_resource "Cloud Run SA" "headhunter-cloudrun-sa" "gcloud iam service-accounts describe headhunter-cloudrun-sa@$PROJECT_ID.iam.gserviceaccount.com"

echo ""
echo -e "${YELLOW}3. Checking IAM Roles...${NC}"
echo "-------------------------"

# Check Functions SA roles
echo -e "Functions SA roles:"
EXPECTED_ROLES=(
    "roles/datastore.user"
    "roles/storage.objectAdmin"
    "roles/secretmanager.secretAccessor"
    "roles/logging.logWriter"
)

for role in "${EXPECTED_ROLES[@]}"; do
    echo -n "  $role... "
    if gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" --filter="bindings.members:serviceAccount:headhunter-functions-sa@$PROJECT_ID.iam.gserviceaccount.com AND bindings.role:$role" --format="value(bindings.role)" | grep -q "$role"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        ((ERRORS++))
    fi
done

# Check Cloud Run SA roles (should NOT have Pub/Sub roles)
echo -e "Cloud Run SA roles:"
CLOUDRUN_EXPECTED_ROLES=(
    "roles/datastore.user"
    "roles/storage.objectAdmin"
    "roles/secretmanager.secretAccessor"
    "roles/logging.logWriter"
)

for role in "${CLOUDRUN_EXPECTED_ROLES[@]}"; do
    echo -n "  $role... "
    if gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" --filter="bindings.members:serviceAccount:headhunter-cloudrun-sa@$PROJECT_ID.iam.gserviceaccount.com AND bindings.role:$role" --format="value(bindings.role)" | grep -q "$role"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        ((ERRORS++))
    fi
done

# Check for unwanted Pub/Sub roles
echo -n "  Checking NO Pub/Sub roles... "
if gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" --filter="bindings.members:serviceAccount:headhunter-cloudrun-sa@$PROJECT_ID.iam.gserviceaccount.com AND (bindings.role:roles/pubsub.publisher OR bindings.role:roles/pubsub.subscriber)" --format="value(bindings.role)" | grep -q "pubsub"; then
    echo -e "${RED}✗ (Pub/Sub roles found - should be removed)${NC}"
    ((ERRORS++))
else
    echo -e "${GREEN}✓${NC}"
fi

echo ""
echo -e "${YELLOW}4. Checking Storage Buckets...${NC}"
echo "-------------------------------"

# Check buckets exist and their regions
for bucket_suffix in "profiles" "files"; do
    bucket_name="${PROJECT_ID}-${bucket_suffix}"
    echo -n "Bucket: $bucket_name... "

    if gsutil ls -b gs://$bucket_name >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"

        # Check region
        location=$(gsutil ls -L -b gs://$bucket_name 2>/dev/null | grep "Location constraint:" | awk '{print $3}')
        check_region "Bucket $bucket_name" "US-CENTRAL1" "$location"
    else
        echo -e "${RED}✗${NC}"
        ((ERRORS++))
    fi
done

echo ""
echo -e "${YELLOW}5. Checking Firestore...${NC}"
echo "------------------------"

echo -n "Firestore database... "
if gcloud firestore databases describe 2>/dev/null | grep -q "name:"; then
    echo -e "${GREEN}✓${NC}"

    # Check region
    location=$(gcloud firestore databases describe --format="value(locationId)" 2>/dev/null)
    check_region "Firestore" "us-central1" "$location"
else
    echo -e "${RED}✗${NC}"
    ((ERRORS++))
fi

echo ""
echo -e "${YELLOW}6. Checking Secret Manager...${NC}"
echo "------------------------------"

echo -n "Secret: TOGETHER_API_KEY... "
if gcloud secrets describe TOGETHER_API_KEY --project $PROJECT_ID >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"

    # Check replication policy
    echo -n "  Replication policy... "
    replication=$(gcloud secrets describe TOGETHER_API_KEY --project $PROJECT_ID --format="value(replication.userManaged.replicas[0].location)" 2>/dev/null || echo "automatic")

    if [[ "$replication" == "us-central1" ]]; then
        echo -e "${GREEN}✓ user-managed (us-central1)${NC}"
    elif [[ "$replication" == "automatic" ]]; then
        echo -e "${YELLOW}⚠ automatic (should be user-managed in us-central1)${NC}"
        ((WARNINGS++))
    else
        echo -e "${YELLOW}⚠ $replication${NC}"
        ((WARNINGS++))
    fi

    # Check IAM bindings
    echo "  Checking IAM bindings:"
    for sa in "headhunter-functions-sa" "headhunter-cloudrun-sa"; do
        echo -n "    $sa... "
        if gcloud secrets get-iam-policy TOGETHER_API_KEY --project $PROJECT_ID --flatten="bindings[].members" --filter="bindings.members:serviceAccount:$sa@$PROJECT_ID.iam.gserviceaccount.com" --format="value(bindings.members)" 2>/dev/null | grep -q "$sa"; then
            echo -e "${GREEN}✓${NC}"
        else
            echo -e "${RED}✗${NC}"
            ((ERRORS++))
        fi
    done
else
    echo -e "${RED}✗${NC}"
    ((ERRORS++))
fi

echo ""
echo -e "${YELLOW}7. Checking Firebase...${NC}"
echo "-----------------------"

echo -n "Firebase project... "
if firebase projects:list --json 2>/dev/null | grep -q "\"projectId\":\"$PROJECT_ID\""; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠ Not initialized (run: firebase projects:addfirebase $PROJECT_ID)${NC}"
    ((WARNINGS++))
fi

echo ""
echo "============================================================"
echo -e "${BLUE}Validation Summary:${NC}"
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Infrastructure is ready.${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Validation completed with $WARNINGS warning(s).${NC}"
    echo "Infrastructure is functional but some optimizations are recommended."
    exit 0
else
    echo -e "${RED}❌ Validation failed with $ERRORS error(s) and $WARNINGS warning(s).${NC}"
    echo "Please run setup_gcp_infrastructure.sh to fix the issues."
    exit 1
fi
