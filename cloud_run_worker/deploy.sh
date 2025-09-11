#!/bin/bash

# Cloud Run deployment script for candidate enricher service
set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-"your-project-id"}
REGION=${REGION:-"us-central1"}
SERVICE_NAME="candidate-enricher"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${BLUE}INFO:${NC} $1"
}

echo_success() {
    echo -e "${GREEN}SUCCESS:${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

echo_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

# Check if PROJECT_ID is set
if [ "$PROJECT_ID" = "your-project-id" ]; then
    echo_error "Please set PROJECT_ID environment variable"
    echo "Example: export PROJECT_ID=my-gcp-project"
    exit 1
fi

# Check if required tools are installed
check_tools() {
    echo_info "Checking required tools..."
    
    if ! command -v gcloud &> /dev/null; then
        echo_error "gcloud CLI is required but not installed"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        echo_error "Docker is required but not installed"
        exit 1
    fi
    
    echo_success "All required tools are available"
}

# Set up GCP project
setup_project() {
    echo_info "Setting up GCP project: $PROJECT_ID"
    
    gcloud config set project $PROJECT_ID
    gcloud auth configure-docker gcr.io
    
    # Enable required APIs
    echo_info "Enabling required APIs..."
    gcloud services enable cloudbuild.googleapis.com
    gcloud services enable run.googleapis.com
    gcloud services enable firestore.googleapis.com
    gcloud services enable pubsub.googleapis.com
    
    echo_success "Project setup complete"
}

# Create service account and permissions
setup_iam() {
    echo_info "Setting up IAM and service accounts..."
    
    # Create service account
    gcloud iam service-accounts create candidate-enricher-sa \
        --display-name="Candidate Enricher Service Account" \
        --project=$PROJECT_ID || echo_warning "Service account may already exist"
    
    # Grant necessary permissions
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:candidate-enricher-sa@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/datastore.user"
    
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:candidate-enricher-sa@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/pubsub.subscriber"
    
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:candidate-enricher-sa@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/pubsub.publisher"
    
    echo_success "IAM setup complete"
}

# Create Pub/Sub topics and subscriptions
setup_pubsub() {
    echo_info "Setting up Pub/Sub topics and subscriptions..."
    
    # Create topics
    gcloud pubsub topics create candidate-enrichment --project=$PROJECT_ID || echo_warning "Topic may already exist"
    gcloud pubsub topics create candidate-processing-dlq --project=$PROJECT_ID || echo_warning "DLQ topic may already exist"
    
    echo_success "Pub/Sub setup complete"
}

# Build and push Docker image
build_image() {
    echo_info "Building Docker image..."
    
    # Build image
    docker build -t $IMAGE_NAME:latest .
    
    # Tag with timestamp for versioning
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    docker tag $IMAGE_NAME:latest $IMAGE_NAME:$TIMESTAMP
    
    echo_info "Pushing Docker image to GCR..."
    docker push $IMAGE_NAME:latest
    docker push $IMAGE_NAME:$TIMESTAMP
    
    echo_success "Docker image built and pushed"
}

# Deploy to Cloud Run
deploy_service() {
    echo_info "Deploying to Cloud Run..."
    
    # Update cloud-run.yaml with actual project ID
    sed "s/PROJECT_ID/$PROJECT_ID/g" cloud-run.yaml > cloud-run-deploy.yaml
    
    # Deploy service
    gcloud run services replace cloud-run-deploy.yaml \
        --region=$REGION \
        --project=$PROJECT_ID
    
    # Get service URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(status.url)")
    
    echo_success "Service deployed successfully"
    echo_info "Service URL: $SERVICE_URL"
    
    # Update Pub/Sub subscription with actual URL
    echo_info "Creating Pub/Sub subscription..."
    gcloud pubsub subscriptions create candidate-enrichment-sub \
        --topic=candidate-enrichment \
        --push-endpoint="$SERVICE_URL/pubsub/webhook" \
        --push-auth-service-account=candidate-enricher-sa@$PROJECT_ID.iam.gserviceaccount.com \
        --ack-deadline=600 \
        --min-retry-delay=10s \
        --max-retry-delay=600s \
        --dead-letter-topic=candidate-processing-dlq \
        --max-delivery-attempts=5 \
        --project=$PROJECT_ID || echo_warning "Subscription may already exist"
    
    # Clean up temporary file
    rm -f cloud-run-deploy.yaml
}

# Create secrets
setup_secrets() {
    echo_info "Setting up secrets..."
    
    if [ -z "$TOGETHER_AI_API_KEY" ]; then
        echo_warning "TOGETHER_AI_API_KEY not set. Please create the secret manually:"
        echo "gcloud secrets create together-ai-credentials --project=$PROJECT_ID"
        echo "echo -n 'your-api-key' | gcloud secrets versions add together-ai-credentials --data-file=- --project=$PROJECT_ID"
    else
        gcloud secrets create together-ai-credentials --project=$PROJECT_ID || echo_warning "Secret may already exist"
        echo -n "$TOGETHER_AI_API_KEY" | gcloud secrets versions add together-ai-credentials --data-file=- --project=$PROJECT_ID
        
        # Grant service account access to secret
        gcloud secrets add-iam-policy-binding together-ai-credentials \
            --member="serviceAccount:candidate-enricher-sa@$PROJECT_ID.iam.gserviceaccount.com" \
            --role="roles/secretmanager.secretAccessor" \
            --project=$PROJECT_ID
    fi
    
    echo_success "Secrets setup complete"
}

# Test deployment
test_deployment() {
    echo_info "Testing deployment..."
    
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(status.url)")
    
    # Test health endpoint
    if curl -f "$SERVICE_URL/health" > /dev/null 2>&1; then
        echo_success "Health check passed"
    else
        echo_error "Health check failed"
        exit 1
    fi
    
    # Test metrics endpoint
    if curl -f "$SERVICE_URL/metrics" > /dev/null 2>&1; then
        echo_success "Metrics endpoint accessible"
    else
        echo_warning "Metrics endpoint may not be accessible"
    fi
    
    echo_success "Deployment test complete"
}

# Main deployment flow
main() {
    echo_info "Starting deployment of candidate enricher service..."
    echo_info "Project: $PROJECT_ID"
    echo_info "Region: $REGION"
    echo_info "Service: $SERVICE_NAME"
    echo ""
    
    check_tools
    setup_project
    setup_iam
    setup_pubsub
    setup_secrets
    build_image
    deploy_service
    test_deployment
    
    echo ""
    echo_success "Deployment completed successfully!"
    echo_info "Service URL: $(gcloud run services describe $SERVICE_NAME --region=$REGION --project=$PROJECT_ID --format='value(status.url)')"
    echo_info "To monitor logs: gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME' --project=$PROJECT_ID --limit=50 --format='table(timestamp,severity,textPayload)'"
}

# Parse command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "build")
        check_tools
        build_image
        ;;
    "test")
        test_deployment
        ;;
    "setup")
        check_tools
        setup_project
        setup_iam
        setup_pubsub
        setup_secrets
        ;;
    "help")
        echo "Usage: $0 [command]"
        echo "Commands:"
        echo "  deploy    - Full deployment (default)"
        echo "  build     - Build and push Docker image only"
        echo "  test      - Test deployed service"
        echo "  setup     - Setup GCP resources only"
        echo "  help      - Show this help"
        ;;
    *)
        echo_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac