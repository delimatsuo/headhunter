#!/usr/bin/env bash
set -euo pipefail

# Deploy hh-search-svc with RERANK_SERVICE_AUDIENCE environment variable
# This script adds the missing environment variable to enable rerank service integration

PROJECT_ID="headhunter-ai-0088"
REGION="us-central1"
SERVICE="hh-search-svc-production"

echo "Adding RERANK_SERVICE_AUDIENCE to $SERVICE..."

# Get current service configuration
CURRENT_CONFIG=$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT_ID" --format=yaml)

# Create a temporary file with the updated configuration
TEMP_FILE=$(mktemp)
echo "$CURRENT_CONFIG" > "$TEMP_FILE"

# Add RERANK_SERVICE_AUDIENCE if not present
if ! grep -q "RERANK_SERVICE_AUDIENCE" "$TEMP_FILE"; then
  echo "Adding RERANK_SERVICE_AUDIENCE environment variable..."

  # Use yq or manual editing to add the env var
  # For now, use gcloud with the full env var list

  # Get all current environment variables
  ENV_VARS=$(gcloud run services describe "$SERVICE" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format="value(spec.template.spec.containers[0].env[].name,spec.template.spec.containers[0].env[].value)" | \
    paste - - | \
    awk '{printf "%s=%s,", $1, $2}' | \
    sed 's/,$//')

  # Add the new environment variable
  NEW_ENV_VARS="${ENV_VARS},RERANK_SERVICE_AUDIENCE=https://hh-rerank-svc-production-akcoqbr7sa-uc.a.run.app"

  echo "Deploying with updated environment variables..."
  gcloud run services update "$SERVICE" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --set-env-vars="$NEW_ENV_VARS"
else
  echo "RERANK_SERVICE_AUDIENCE already present"
fi

rm -f "$TEMP_FILE"

echo "Deployment complete!"
echo "Verifying environment variables..."
gcloud run services describe "$SERVICE" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format="value(spec.template.spec.containers[0].env)" | \
  tr ';' '\n' | \
  grep -i rerank
