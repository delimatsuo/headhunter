#!/bin/bash
"""
Deployment script for Headhunter AI Cloud Functions
"""

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project configuration
PROJECT_ID="headhunter-ai-0088"
REGION="us-central1"
FUNCTIONS_DIR="functions"

echo -e "${BLUE}🚀 Deploying Headhunter AI Cloud Functions${NC}"
echo "================================================"

# Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI is not installed${NC}"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if firebase CLI is installed
if ! command -v firebase &> /dev/null; then
    echo -e "${RED}❌ Firebase CLI is not installed${NC}"
    echo "Install with: npm install -g firebase-tools"
    exit 1
fi

# Check if logged in to gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n 1 > /dev/null; then
    echo -e "${RED}❌ Not logged in to gcloud${NC}"
    echo "Run: gcloud auth login"
    exit 1
fi

# Check if logged in to firebase
if ! firebase login:list --json | grep -q "user"; then
    echo -e "${RED}❌ Not logged in to Firebase${NC}"
    echo "Run: firebase login"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Set gcloud project
echo -e "${YELLOW}🔧 Setting gcloud project to ${PROJECT_ID}...${NC}"
gcloud config set project $PROJECT_ID

# Navigate to functions directory
cd $FUNCTIONS_DIR

# Install dependencies
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
npm install

# Build TypeScript
echo -e "${YELLOW}🔨 Building TypeScript...${NC}"
npm run build

# Run linting
echo -e "${YELLOW}🔍 Running linter...${NC}"
npm run lint || echo -e "${YELLOW}⚠️ Linter warnings detected, continuing...${NC}"

# Run tests (if they pass)
echo -e "${YELLOW}🧪 Running tests...${NC}"
npm test || echo -e "${YELLOW}⚠️ Tests failed or not configured, continuing...${NC}"

# Create storage bucket if it doesn't exist
echo -e "${YELLOW}🪣 Creating storage bucket for profiles...${NC}"
BUCKET_NAME="${PROJECT_ID}-profiles"
if ! gsutil ls -b gs://$BUCKET_NAME > /dev/null 2>&1; then
    gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME
    echo -e "${GREEN}✅ Created bucket: $BUCKET_NAME${NC}"
else
    echo -e "${GREEN}✅ Bucket already exists: $BUCKET_NAME${NC}"
fi

# Deploy functions
echo -e "${YELLOW}🚀 Deploying Cloud Functions...${NC}"
firebase deploy --only functions --project $PROJECT_ID

if [ $? -eq 0 ]; then
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    echo ""
    echo "Functions deployed:"
    echo "- processUploadedProfile (Storage trigger)"
    echo "- healthCheck (HTTPS callable)"
    echo "- enrichProfile (HTTPS callable)"  
    echo "- searchCandidates (HTTPS callable)"
    echo ""
    echo "Test with:"
    echo "  firebase functions:shell --project $PROJECT_ID"
    echo ""
    echo "View logs with:"
    echo "  firebase functions:log --project $PROJECT_ID"
else
    echo -e "${RED}❌ Deployment failed${NC}"
    exit 1
fi