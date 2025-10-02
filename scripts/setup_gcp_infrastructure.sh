#!/bin/bash
set -e


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Headhunter AI - GCP Infrastructure Setup Script
# This script sets up the complete Google Cloud Platform infrastructure for Headhunter AI

PROJECT_NAME="Headhunter AI"
PROJECT_ID=""
SERVICE_ACCOUNT_NAME="headhunter-service"
BILLING_ACCOUNT_ID=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# Function to check if gcloud is installed and authenticated
check_gcloud() {
    print_header "Checking Google Cloud CLI"
    
    if ! command -v gcloud &> /dev/null; then
        print_error "Google Cloud CLI is not installed"
        print_status "Please install it from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    print_status "Google Cloud CLI is installed"
    gcloud version
    
    # Check if authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null; then
        print_error "Not authenticated with Google Cloud"
        print_status "Please run: gcloud auth login"
        exit 1
    fi
    
    ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1)
    print_status "Authenticated as: $ACTIVE_ACCOUNT"
}

# Function to get or create project
setup_project() {
    print_header "Setting up GCP Project"
    
    if [ -z "$PROJECT_ID" ]; then
        PROJECT_ID="headhunter-ai-$(date +%s | tail -c 5)"
        print_status "Creating new project: $PROJECT_ID"
        
        gcloud projects create $PROJECT_ID --name="$PROJECT_NAME"
        print_status "Project $PROJECT_ID created successfully"
    else
        print_status "Using existing project: $PROJECT_ID"
    fi
    
    # Set as active project
    gcloud config set project $PROJECT_ID
    print_status "Set $PROJECT_ID as active project"
}

# Function to link billing account
setup_billing() {
    print_header "Setting up Billing"
    
    # List available billing accounts
    echo "Available billing accounts:"
    gcloud billing accounts list
    
    if [ -z "$BILLING_ACCOUNT_ID" ]; then
        # Get the first available billing account
        BILLING_ACCOUNT_ID=$(gcloud billing accounts list --filter="open:true" --format="value(name)" | head -1)
        BILLING_ACCOUNT_ID=${BILLING_ACCOUNT_ID##*/}
    fi
    
    if [ -n "$BILLING_ACCOUNT_ID" ]; then
        gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT_ID
        print_status "Linked billing account: $BILLING_ACCOUNT_ID"
    else
        print_warning "No billing account found. Some services may not work without billing enabled."
    fi
}

# Function to enable required APIs
enable_apis() {
    print_header "Enabling Required APIs"
    
    APIs=(
        "aiplatform.googleapis.com"              # Vertex AI
        "firestore.googleapis.com"               # Firestore
        "storage.googleapis.com"                 # Cloud Storage  
        "cloudfunctions.googleapis.com"          # Cloud Functions
        "firebase.googleapis.com"                # Firebase
        "artifactregistry.googleapis.com"       # Artifact Registry
        "run.googleapis.com"                     # Cloud Run
        "cloudbuild.googleapis.com"              # Cloud Build
    )
    
    for api in "${APIs[@]}"; do
        print_status "Enabling $api..."
        gcloud services enable $api
    done
    
    print_status "All APIs enabled successfully"
}

# Function to create service account and assign IAM roles
setup_service_account() {
    print_header "Setting up Service Account"
    
    # Create service account
    print_status "Creating service account: $SERVICE_ACCOUNT_NAME"
    gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
        --display-name="Headhunter AI Service Account" \
        --description="Service account for Headhunter AI application"
    
    SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"
    print_status "Service account created: $SERVICE_ACCOUNT_EMAIL"
    
    # Assign IAM roles
    print_status "Assigning IAM roles..."
    ROLES=(
        "roles/aiplatform.user"
        "roles/datastore.user"
        "roles/storage.objectAdmin"
        "roles/cloudfunctions.invoker"
    )
    
    for role in "${ROLES[@]}"; do
        print_status "Assigning role: $role"
        gcloud projects add-iam-policy-binding $PROJECT_ID \
            --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
            --role="$role"
    done
    
    # Create service account key
    CREDENTIALS_DIR="../.gcp"
    mkdir -p "$CREDENTIALS_DIR"
    KEY_FILE="$CREDENTIALS_DIR/headhunter-service-key.json"
    
    print_status "Creating service account key..."
    gcloud iam service-accounts keys create "$KEY_FILE" \
        --iam-account="$SERVICE_ACCOUNT_EMAIL"
    
    print_status "Service account key saved to: $KEY_FILE"
    print_warning "Keep this key file secure and do not commit it to version control"
}

# Function to setup Firebase
setup_firebase() {
    print_header "Setting up Firebase"
    
    # Check if Firebase CLI is installed
    if ! command -v firebase &> /dev/null; then
        print_error "Firebase CLI is not installed"
        print_status "Please install it with: npm install -g firebase-tools"
        return 1
    fi
    
    print_status "Adding Firebase to project..."
    firebase projects:addfirebase $PROJECT_ID 2>/dev/null || true
    
    print_status "Firebase configuration files are already created in the project directory"
    print_status "Firebase project ready at: https://console.firebase.google.com/project/$PROJECT_ID"
}

# Function to create Cloud Storage buckets
setup_storage() {
    print_header "Setting up Cloud Storage"
    
    BUCKETS=(
        "$PROJECT_ID-resumes"
        "$PROJECT_ID-profiles"
        "$PROJECT_ID-embeddings"
    )
    
    for bucket in "${BUCKETS[@]}"; do
        print_status "Creating bucket: gs://$bucket"
        gsutil mb -p $PROJECT_ID gs://$bucket/ 2>/dev/null || print_warning "Bucket $bucket may already exist"
        
        # Set bucket permissions
        gsutil iam ch serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com:objectAdmin gs://$bucket/
    done
    
    print_status "Cloud Storage buckets created and configured"
}

# Function to initialize Firestore
setup_firestore() {
    print_header "Setting up Firestore"
    
    print_status "Creating Firestore database..."
    gcloud firestore databases create --region=us-central1 2>/dev/null || print_warning "Firestore database may already exist"
    
    print_status "Firestore database ready"
    print_status "Security rules and indexes are configured in firestore.rules and firestore.indexes.json"
}

# Function to display summary
display_summary() {
    print_header "Setup Complete!"
    
    echo -e "${GREEN}Project Information:${NC}"
    echo "  Project ID: $PROJECT_ID"
    echo "  Project Name: $PROJECT_NAME"
    echo "  Service Account: $SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"
    echo ""
    echo -e "${GREEN}Console URLs:${NC}"
    echo "  GCP Console: https://console.cloud.google.com/home/dashboard?project=$PROJECT_ID"
    echo "  Firebase Console: https://console.firebase.google.com/project/$PROJECT_ID"
    echo "  Vertex AI: https://console.cloud.google.com/vertex-ai?project=$PROJECT_ID"
    echo "  Firestore: https://console.cloud.google.com/firestore?project=$PROJECT_ID"
    echo ""
    echo -e "${GREEN}Environment Setup:${NC}"
    echo "  export GOOGLE_APPLICATION_CREDENTIALS=\"$(pwd)/../.gcp/headhunter-service-key.json\""
    echo "  export GOOGLE_CLOUD_PROJECT=\"$PROJECT_ID\""
    echo ""
    echo -e "${GREEN}Next Steps:${NC}"
    echo "  1. Test the infrastructure with: ./test_gcp_connectivity.sh"
    echo "  2. Deploy Firebase security rules: firebase deploy --only firestore:rules"
    echo "  3. Deploy Firebase functions: firebase deploy --only functions"
    echo "  4. Deploy Firebase hosting: firebase deploy --only hosting"
}

# Main execution
main() {
    print_header "Headhunter AI - GCP Infrastructure Setup"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --project-id)
                PROJECT_ID="$2"
                shift 2
                ;;
            --billing-account)
                BILLING_ACCOUNT_ID="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                echo "Usage: $0 [--project-id PROJECT_ID] [--billing-account BILLING_ACCOUNT_ID]"
                exit 1
                ;;
        esac
    done
    
    check_gcloud
    setup_project
    setup_billing
    enable_apis
    setup_service_account
    setup_firebase
    setup_storage
    setup_firestore
    display_summary
}

# Run main function
main "$@"
