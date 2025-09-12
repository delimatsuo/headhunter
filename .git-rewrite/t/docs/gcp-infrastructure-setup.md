# Google Cloud Platform Infrastructure Setup

This document describes the complete GCP infrastructure setup for Headhunter AI, including all services, configurations, and deployment instructions.

## Overview

Headhunter AI uses the following GCP services:
- **Vertex AI**: For enhanced LLM processing and model deployment
- **Firestore**: For structured data storage (candidate profiles, searches)
- **Cloud Storage**: For file storage (resumes, processed profiles)
- **Cloud Functions**: For serverless API endpoints
- **Firebase Hosting**: For web application deployment
- **Firebase Authentication**: For user management (future)

## Project Information

- **Project ID**: `headhunter-ai-0088`
- **Project Name**: Headhunter AI
- **Region**: us-central1
- **Service Account**: `headhunter-service@headhunter-ai-0088.iam.gserviceaccount.com`

## Console URLs

- **GCP Console**: https://console.cloud.google.com/home/dashboard?project=headhunter-ai-0088
- **Firebase Console**: https://console.firebase.google.com/project/headhunter-ai-0088
- **Vertex AI**: https://console.cloud.google.com/vertex-ai?project=headhunter-ai-0088
- **Firestore**: https://console.cloud.google.com/firestore?project=headhunter-ai-0088

## Prerequisites

1. **Google Cloud CLI** installed and authenticated
2. **Firebase CLI** installed and authenticated
3. **Node.js 20+** for Cloud Functions
4. **Python 3.8+** with required Google Cloud libraries

### Installation Commands

```bash
# Install Google Cloud libraries
pip install google-cloud-aiplatform google-cloud-firestore google-cloud-storage

# Install Firebase CLI (if not already installed)
npm install -g firebase-tools
```

## Automated Setup

Use the automated setup script for new environments:

```bash
# Run the setup script
./scripts/setup_gcp_infrastructure.sh

# Test connectivity
python scripts/test_gcp_connectivity.py
```

## Manual Setup Steps

### 1. Create GCP Project

```bash
# Create new project
gcloud projects create headhunter-ai-XXXXX --name="Headhunter AI"

# Set as active project
gcloud config set project headhunter-ai-XXXXX
```

### 2. Enable Billing

```bash
# List billing accounts
gcloud billing accounts list

# Link billing account
gcloud billing projects link headhunter-ai-XXXXX --billing-account=BILLING_ACCOUNT_ID
```

### 3. Enable Required APIs

```bash
gcloud services enable aiplatform.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable firebase.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### 4. Create Service Account

```bash
# Create service account
gcloud iam service-accounts create headhunter-service \
    --display-name="Headhunter AI Service Account"

# Assign IAM roles
gcloud projects add-iam-policy-binding headhunter-ai-XXXXX \
    --member="serviceAccount:headhunter-service@headhunter-ai-XXXXX.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding headhunter-ai-XXXXX \
    --member="serviceAccount:headhunter-service@headhunter-ai-XXXXX.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding headhunter-ai-XXXXX \
    --member="serviceAccount:headhunter-service@headhunter-ai-XXXXX.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding headhunter-ai-XXXXX \
    --member="serviceAccount:headhunter-service@headhunter-ai-XXXXX.iam.gserviceaccount.com" \
    --role="roles/cloudfunctions.invoker"

# Create service account key
mkdir -p .gcp
gcloud iam service-accounts keys create .gcp/headhunter-service-key.json \
    --iam-account=headhunter-service@headhunter-ai-XXXXX.iam.gserviceaccount.com
```

### 5. Setup Firebase

```bash
# Add Firebase to project
firebase projects:addfirebase headhunter-ai-XXXXX

# Initialize Firebase (configuration files are already created)
# firebase init --project headhunter-ai-XXXXX
```

### 6. Create Firestore Database

```bash
gcloud firestore databases create --location=us-central1
```

### 7. Setup Cloud Storage Buckets (Optional)

```bash
# Create buckets for file storage
gsutil mb -p headhunter-ai-XXXXX gs://headhunter-ai-XXXXX-resumes/
gsutil mb -p headhunter-ai-XXXXX gs://headhunter-ai-XXXXX-profiles/
gsutil mb -p headhunter-ai-XXXXX gs://headhunter-ai-XXXXX-embeddings/
```

## Firebase Configuration

### firestore.rules
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow authenticated users to read and write their own data
    match /candidates/{candidateId} {
      allow read, write: if request.auth != null;
    }
    
    match /searches/{searchId} {
      allow read, write: if request.auth != null;
    }
    
    match /job_descriptions/{jobId} {
      allow read, write: if request.auth != null;
    }
    
    // Vector embeddings collection
    match /embeddings/{embeddingId} {
      allow read: if request.auth != null;
      allow write: if request.auth != null && request.auth.uid == resource.data.created_by;
    }
  }
}
```

### firestore.indexes.json
Composite indexes for efficient queries on:
- Candidates by score and processed_at
- Candidates by recommendation and score
- Searches by created_at and created_by

## Environment Setup

### Local Development

```bash
# Set environment variables
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/.gcp/headhunter-service-key.json"
export GOOGLE_CLOUD_PROJECT="headhunter-ai-0088"

# Verify setup
python scripts/test_gcp_connectivity.py
```

### Production Deployment

For production deployments, use service account keys through secure secret management rather than environment variables.

## Firebase Deployment

### Deploy Security Rules
```bash
firebase deploy --only firestore:rules
firebase deploy --only firestore:indexes
firebase deploy --only storage
```

### Deploy Functions
```bash
cd functions
npm install
cd ..
firebase deploy --only functions
```

### Deploy Hosting
```bash
firebase deploy --only hosting
```

## Monitoring and Logging

### Cloud Logging
- Function execution logs: Cloud Functions > Logs
- Firestore operations: Firestore > Usage
- API usage: APIs & Services > Dashboard

### Error Monitoring
- Cloud Error Reporting automatically tracks errors
- Custom metrics can be added using Cloud Monitoring

## Security Best Practices

1. **Service Account Keys**: Store securely, never commit to version control
2. **IAM Permissions**: Use principle of least privilege
3. **Firestore Rules**: Validate all database access
4. **API Keys**: Restrict by referrer/IP when possible
5. **Regular Audits**: Review IAM bindings and access logs

## Cost Optimization

1. **Firestore**: Use native mode, monitor read/write operations
2. **Cloud Functions**: Optimize memory allocation and execution time
3. **Storage**: Use lifecycle policies for old files
4. **Vertex AI**: Monitor model prediction costs
5. **Alerts**: Set up billing alerts for unexpected usage

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   ```bash
   gcloud auth application-default login
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-key.json"
   ```

2. **Permission Denied**
   - Verify service account has required roles
   - Check IAM bindings with `gcloud projects get-iam-policy`

3. **Firestore Not Found**
   ```bash
   gcloud firestore databases create --location=us-central1
   ```

4. **Function Deployment Issues**
   - Check Node.js version (should be 20+)
   - Verify billing is enabled
   - Check function logs in Cloud Console

### Testing Connectivity

Run the connectivity test script to verify all services:

```bash
python scripts/test_gcp_connectivity.py
```

Expected output should show all tests passing:
- ✅ Python Imports
- ✅ Credentials
- ✅ Firebase Config
- ✅ Firestore
- ✅ Cloud Storage
- ✅ Vertex AI

## Next Steps

1. **Deploy Cloud Functions**: Implement candidate processing and search endpoints
2. **Set up Vector Search**: Configure Vertex AI Vector Search for semantic matching
3. **Build Web Interface**: Create React application for candidate search
4. **Configure Authentication**: Add Firebase Auth for user management
5. **Set up CI/CD**: Automate deployments with GitHub Actions

## Support

For issues related to:
- **GCP Services**: [Google Cloud Support](https://cloud.google.com/support)
- **Firebase**: [Firebase Support](https://firebase.google.com/support)
- **This Project**: Create an issue in the project repository