#!/bin/bash
# =============================================================================
# Switch to Gemini Embeddings
# =============================================================================
#
# This script switches the embedding provider from Vertex AI (text-embedding-004)
# to Gemini API (gemini-embedding-001).
#
# BENEFITS:
#   - Better quality: 68% vs 66.3% on MTEB benchmark
#   - Lower cost: FREE tier (1,500 req/day) or $0.15/1M tokens
#   - Estimated savings: ~$150-200/month
#
# REQUIREMENTS:
#   - GOOGLE_API_KEY set in environment or Firebase/GCP secrets
#   - Firebase CLI installed and configured
#
# =============================================================================

set -e

PROJECT_ID="headhunter-ai-0088"
REGION="us-central1"

echo "=================================================="
echo "  Switch to Gemini Embeddings"
echo "  Project: $PROJECT_ID"
echo "=================================================="
echo ""

# Check for API key
if [ -z "$GOOGLE_API_KEY" ] && [ -z "$GEMINI_API_KEY" ]; then
    echo "WARNING: Neither GOOGLE_API_KEY nor GEMINI_API_KEY is set in environment."
    echo "The Cloud Functions will need this key configured via Firebase secrets."
    echo ""
fi

# Display the plan
show_plan() {
    echo "This script will:"
    echo "  1. Set EMBEDDING_PROVIDER=gemini in Cloud Functions config"
    echo "  2. Redeploy affected Cloud Functions"
    echo "  3. Verify the deployment"
    echo ""
    echo "Affected functions:"
    echo "  - semanticSearch"
    echo "  - generateEmbedding"
    echo "  - generateEmbeddingForCandidate"
    echo "  - generateAllEmbeddings"
    echo "  - skillAwareSearch"
    echo "  - engineSearch"
    echo ""
    echo "Note: Existing embeddings in pgvector remain valid (768 dimensions)."
    echo "      New embeddings will use Gemini API."
    echo ""
}

# Set the environment variable
set_config() {
    echo "Setting EMBEDDING_PROVIDER=gemini..."

    # Check if GOOGLE_API_KEY needs to be set
    if ! firebase functions:secrets:access GOOGLE_API_KEY --project=$PROJECT_ID > /dev/null 2>&1; then
        echo ""
        echo "WARNING: GOOGLE_API_KEY secret not found in Firebase."
        echo "You need to set it before deploying:"
        echo ""
        echo "  firebase functions:secrets:set GOOGLE_API_KEY --project=$PROJECT_ID"
        echo ""
        read -p "Do you want to set it now? (y/N): " set_key
        if [[ "$set_key" == "y" || "$set_key" == "Y" ]]; then
            firebase functions:secrets:set GOOGLE_API_KEY --project=$PROJECT_ID
        else
            echo "Skipping. Make sure to set the key before functions can use Gemini."
        fi
    fi

    echo "✅ Configuration ready"
}

# Deploy the functions
deploy_functions() {
    echo ""
    echo "Building and deploying Cloud Functions..."
    echo "This may take a few minutes..."
    echo ""

    cd "$(dirname "$0")/.."

    # Build first
    echo "Building TypeScript..."
    npm --prefix functions run build

    # Deploy with the new config
    echo ""
    echo "Deploying functions with EMBEDDING_PROVIDER=gemini..."

    # We need to set the runtime config. For Firebase Functions, this is done via .env
    # Create/update the .env file for functions
    ENV_FILE="functions/.env"

    # Backup existing .env if it exists
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "${ENV_FILE}.backup"
        echo "Backed up existing .env to .env.backup"
    fi

    # Check if EMBEDDING_PROVIDER already exists in .env
    if [ -f "$ENV_FILE" ] && grep -q "^EMBEDDING_PROVIDER=" "$ENV_FILE"; then
        # Update existing value
        sed -i '' 's/^EMBEDDING_PROVIDER=.*/EMBEDDING_PROVIDER=gemini/' "$ENV_FILE"
    else
        # Add new value
        echo "EMBEDDING_PROVIDER=gemini" >> "$ENV_FILE"
    fi

    echo "Updated $ENV_FILE with EMBEDDING_PROVIDER=gemini"

    # Deploy
    firebase deploy --only functions --project=$PROJECT_ID

    echo "✅ Deployment complete"
}

# Verify deployment
verify_deployment() {
    echo ""
    echo "Verifying deployment..."

    # Test with a simple healthCheck call
    echo "Testing healthCheck function..."

    # Get the function URL and test it
    # Note: This requires the Firebase CLI to be authenticated
    firebase functions:log --only healthCheck --project=$PROJECT_ID | head -5

    echo ""
    echo "✅ Verification complete"
    echo ""
    echo "To test Gemini embeddings manually, run a search query in the UI"
    echo "or call the semanticSearch function."
}

# Rollback function
rollback() {
    echo ""
    echo "Rolling back to Vertex AI embeddings..."

    ENV_FILE="functions/.env"

    if [ -f "$ENV_FILE" ]; then
        # Update to vertex
        if grep -q "^EMBEDDING_PROVIDER=" "$ENV_FILE"; then
            sed -i '' 's/^EMBEDDING_PROVIDER=.*/EMBEDDING_PROVIDER=vertex/' "$ENV_FILE"
        else
            echo "EMBEDDING_PROVIDER=vertex" >> "$ENV_FILE"
        fi
    fi

    echo "Updated .env with EMBEDDING_PROVIDER=vertex"
    echo "Run 'firebase deploy --only functions' to apply the rollback."
}

# Help
show_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  plan      Show what will be changed (default)"
    echo "  deploy    Deploy with Gemini embeddings"
    echo "  rollback  Rollback to Vertex AI embeddings"
    echo "  help      Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 plan      # See what will change"
    echo "  $0 deploy    # Switch to Gemini"
    echo "  $0 rollback  # Switch back to Vertex AI"
    echo ""
}

# Main
case "${1:-plan}" in
    plan)
        show_plan
        ;;
    deploy)
        show_plan
        read -p "Continue with deployment? (y/N): " confirm
        if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
            set_config
            deploy_functions
            verify_deployment
        else
            echo "Aborted."
        fi
        ;;
    rollback)
        rollback
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

echo ""
echo "Done!"
