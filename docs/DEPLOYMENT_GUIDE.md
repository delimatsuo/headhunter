# Headhunter AI - Production Deployment Guide

## Overview

This guide covers the complete deployment process for Headhunter AI to Firebase/GCP, including database setup, security configuration, and production optimization.

## Prerequisites

1. **Google Cloud Project**
   - Project ID: `headhunter-ai-0088` (or your chosen project)
   - Billing enabled
   - Firebase enabled

2. **Required APIs**
   ```bash
   gcloud services enable cloudfunctions.googleapis.com
   gcloud services enable firestore.googleapis.com
   gcloud services enable storage-component.googleapis.com
   gcloud services enable firebase.googleapis.com
   gcloud services enable iamcredentials.googleapis.com
   ```

3. **Local Development Tools**
   ```bash
   npm install -g firebase-tools
   npm install -g @google-cloud/cli
   ```

## 🚀 Step 1: Firebase Project Setup

### Initialize Firebase
```bash
cd /path/to/headhunter
firebase login
firebase init
```

Select these features:
- ✅ Firestore
- ✅ Functions
- ✅ Hosting
- ✅ Storage

### Project Configuration
```bash
firebase use headhunter-ai-0088
```

### Set up Firebase Configuration
Update `firebase.json`:
```json
{
  "firestore": {
    "rules": "firestore.rules",
    "indexes": "firestore.indexes.json"
  },
  "functions": [
    {
      "source": "functions",
      "codebase": "default",
      "runtime": "nodejs20"
    }
  ],
  "hosting": {
    "public": "headhunter-ui/build",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [
      {
        "source": "**",
        "destination": "/index.html"
      }
    ]
  },
  "storage": {
    "rules": "storage.rules"
  }
}
```

## 🔒 Step 2: Security Rules Configuration

### Firestore Security Rules (`firestore.rules`)
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Helper functions
    function isAuthenticated() {
      return request.auth != null;
    }
    
    function belongsToOrg(orgId) {
      return isAuthenticated() && 
             get(/databases/$(database)/documents/users/$(request.auth.uid)).data.org_id == orgId;
    }
    
    function hasPermission(permission) {
      return isAuthenticated() && 
             get(/databases/$(database)/documents/users/$(request.auth.uid)).data.permissions[permission] == true;
    }
    
    // Users collection - users can read/write their own document
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    
    // Organizations collection - only org members can read
    match /organizations/{orgId} {
      allow read: if belongsToOrg(orgId);
      allow write: if belongsToOrg(orgId) && hasPermission('can_manage_org');
    }
    
    // Candidates collection - org-scoped access
    match /candidates/{candidateId} {
      allow read: if belongsToOrg(resource.data.org_id) && hasPermission('can_view_candidates');
      allow create: if belongsToOrg(request.resource.data.org_id) && hasPermission('can_edit_candidates');
      allow update: if belongsToOrg(resource.data.org_id) && hasPermission('can_edit_candidates');
      allow delete: if belongsToOrg(resource.data.org_id) && hasPermission('can_edit_candidates');
    }
    
    // Jobs collection - org-scoped access
    match /jobs/{jobId} {
      allow read: if belongsToOrg(resource.data.org_id) && hasPermission('can_view_candidates');
      allow create: if belongsToOrg(request.resource.data.org_id) && hasPermission('can_create_jobs');
      allow update: if belongsToOrg(resource.data.org_id) && hasPermission('can_create_jobs');
      allow delete: if belongsToOrg(resource.data.org_id) && hasPermission('can_create_jobs');
    }
    
    // Embeddings collection - read-only for authenticated users in same org
    match /embeddings/{embeddingId} {
      allow read: if belongsToOrg(resource.data.org_id) && hasPermission('can_view_candidates');
      allow write: if false; // Only Cloud Functions can write
    }
    
    // Processing queue - read-only for org members
    match /processing_queue/{queueId} {
      allow read: if belongsToOrg(resource.data.org_id) && hasPermission('can_view_candidates');
      allow write: if false; // Only Cloud Functions can write
    }
    
    // Search cache - read-only for org members
    match /search_cache/{cacheId} {
      allow read: if belongsToOrg(resource.data.org_id);
      allow write: if false; // Only Cloud Functions can write
    }
    
    // Upload sessions - users can read/write their own sessions
    match /upload_sessions/{sessionId} {
      allow read, write: if isAuthenticated() && 
                            resource.data.uploaded_by == request.auth.uid && 
                            belongsToOrg(resource.data.org_id);
    }
    
    // Activity logs - read-only for org members
    match /activity_logs/{logId} {
      allow read: if belongsToOrg(resource.data.org_id);
      allow write: if false; // Only Cloud Functions can write
    }
    
    // Analytics - read-only for org members
    match /analytics/{analyticsId} {
      allow read: if belongsToOrg(resource.data.org_id);
      allow write: if false; // Only Cloud Functions can write
    }
    
    // Deny all other access
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

### Storage Security Rules (`storage.rules`)
```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    // Organization-scoped file access
    match /organizations/{orgId}/candidates/{candidateId}/{allPaths=**} {
      allow read, write: if request.auth != null &&
                            getUserData().org_id == orgId &&
                            getUserData().permissions.can_edit_candidates == true;
    }
    
    match /organizations/{orgId}/exports/{allPaths=**} {
      allow read: if request.auth != null &&
                     getUserData().org_id == orgId &&
                     getUserData().permissions.can_export_data == true;
    }
    
    // Helper function to get user data
    function getUserData() {
      return firestore.get(/databases/(default)/documents/users/$(request.auth.uid)).data;
    }
    
    // Deny all other access
    match /{allPaths=**} {
      allow read, write: if false;
    }
  }
}
```

## 📊 Step 3: Database Indexes Setup

Create `firestore.indexes.json`:
```json
{
  "indexes": [
    {
      "collectionGroup": "candidates",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "org_id", "order": "ASCENDING" },
        { "fieldPath": "searchable_data.experience_level", "order": "ASCENDING" },
        { "fieldPath": "updated_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "candidates",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "org_id", "order": "ASCENDING" },
        { "fieldPath": "analysis.leadership_scope.has_leadership", "order": "ASCENDING" },
        { "fieldPath": "updated_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "candidates",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "org_id", "order": "ASCENDING" },
        { "fieldPath": "searchable_data.skills_combined", "arrayConfig": "CONTAINS" },
        { "fieldPath": "updated_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "jobs",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "org_id", "order": "ASCENDING" },
        { "fieldPath": "status.is_active", "order": "ASCENDING" },
        { "fieldPath": "updated_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "jobs",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "org_id", "order": "ASCENDING" },
        { "fieldPath": "details.seniority_level", "order": "ASCENDING" },
        { "fieldPath": "status.is_active", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "embeddings",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "org_id", "order": "ASCENDING" },
        { "fieldPath": "metadata.experience_level", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "processing_queue",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "org_id", "order": "ASCENDING" },
        { "fieldPath": "stage", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "ASCENDING" }
      ]
    },
    {
      "collectionGroup": "activity_logs",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "org_id", "order": "ASCENDING" },
        { "fieldPath": "timestamp", "order": "DESCENDING" }
      ]
    }
  ],
  "fieldOverrides": []
}
```

## ⚙️ Step 4: Cloud Functions Configuration

### Environment Configuration
```bash
cd functions

# Set environment variables
firebase functions:config:set \
  app.environment="production" \
  app.cors_origins="https://headhunter-ai-0088.web.app,https://yourdomain.com" \
  storage.bucket_files="headhunter-ai-0088-files" \
  storage.bucket_backups="headhunter-ai-0088-backups" \
  processing.webhook_secret="your-webhook-secret-key" \
  processing.max_file_size="52428800"
```

### Dependencies Installation
```bash
npm install
```

### TypeScript Configuration (`tsconfig.json`)
```json
{
  "compilerOptions": {
    "module": "commonjs",
    "noImplicitReturns": true,
    "noUnusedLocals": true,
    "outDir": "lib",
    "sourceMap": true,
    "strict": true,
    "target": "es2018",
    "lib": ["es2018"],
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "moduleResolution": "node",
    "resolveJsonModule": true
  },
  "compileOnSave": true,
  "include": ["src"]
}
```

### Build and Deploy Functions
```bash
npm run build
firebase deploy --only functions
```

## 🗄️ Step 5: Database Initialization

### Create Initial Collections
```bash
# Deploy Firestore rules and indexes
firebase deploy --only firestore

# Initialize with setup script
node scripts/initialize-database.js
```

Create `scripts/initialize-database.js`:
```javascript
const admin = require('firebase-admin');
const serviceAccount = require('../.gcp/headhunter-service-key.json');

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
  projectId: 'headhunter-ai-0088'
});

const db = admin.firestore();

async function initializeDatabase() {
  // Create system collections with initial documents
  
  // Health check document
  await db.collection('system').doc('health').set({
    status: 'initialized',
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
    version: '1.0.0'
  });
  
  // Default organization template
  await db.collection('organization_templates').doc('default').set({
    name: 'Default Organization',
    settings: {
      data_retention: {
        candidate_data_retention_months: 24,
        activity_log_retention_months: 12
      },
      features: {
        semantic_search: true,
        bulk_operations: true,
        advanced_analytics: true
      }
    },
    permissions_template: {
      admin: {
        can_view_candidates: true,
        can_edit_candidates: true,
        can_create_jobs: true,
        can_export_data: true,
        can_manage_users: true,
        can_manage_org: true
      },
      recruiter: {
        can_view_candidates: true,
        can_edit_candidates: true,
        can_create_jobs: true,
        can_export_data: true,
        can_manage_users: false,
        can_manage_org: false
      },
      hiring_manager: {
        can_view_candidates: true,
        can_edit_candidates: false,
        can_create_jobs: true,
        can_export_data: false,
        can_manage_users: false,
        can_manage_org: false
      },
      viewer: {
        can_view_candidates: true,
        can_edit_candidates: false,
        can_create_jobs: false,
        can_export_data: false,
        can_manage_users: false,
        can_manage_org: false
      }
    }
  });
  
  console.log('Database initialized successfully');
}

initializeDatabase().catch(console.error);
```

## 🌐 Step 6: Frontend Deployment

### Build React App
```bash
cd headhunter-ui
npm install
npm run build
```

### Deploy to Firebase Hosting
```bash
firebase deploy --only hosting
```

### Configure Custom Domain (Optional)
```bash
firebase hosting:channel:deploy production --expires 1d
firebase hosting:channel:clone production:live
```

## 📈 Step 7: Monitoring & Analytics Setup

### Enable Monitoring
```bash
# Enable necessary APIs
gcloud services enable monitoring.googleapis.com
gcloud services enable logging.googleapis.com
gcloud services enable cloudtrace.googleapis.com
```

### Cloud Functions Monitoring
```javascript
// Add to functions/src/monitoring.ts
import { onCall } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";

export const getSystemMetrics = onCall(async (request) => {
  // Collect system metrics
  const metrics = {
    timestamp: new Date().toISOString(),
    functions: {
      invocations_last_hour: await getInvocationCount('1h'),
      average_duration: await getAverageDuration(),
      error_rate: await getErrorRate()
    },
    database: {
      reads_last_hour: await getFirestoreReads('1h'),
      writes_last_hour: await getFirestoreWrites('1h'),
      document_count: await getTotalDocuments()
    },
    storage: {
      total_files: await getStorageFileCount(),
      total_size_gb: await getTotalStorageSize()
    }
  };
  
  return { success: true, metrics };
});
```

### Set up Alerting
```bash
# Create alerting policy for function errors
gcloud alpha monitoring policies create --policy-from-file=monitoring/alert-policies.yaml
```

Create `monitoring/alert-policies.yaml`:
```yaml
displayName: "Cloud Functions High Error Rate"
conditions:
  - displayName: "Error rate > 5%"
    conditionThreshold:
      filter: 'resource.type="cloud_function" resource.label.function_name=~"headhunter.*"'
      comparison: COMPARISON_RATIO_GREATER_THAN
      thresholdValue: 0.05
      duration: "300s"
alertStrategy:
  autoClose: "1800s"
notificationChannels:
  - "projects/headhunter-ai-0088/notificationChannels/EMAIL_CHANNEL_ID"
```

## 🔐 Step 8: Security Hardening

### IAM Roles Configuration
```bash
# Create custom role for Cloud Functions
gcloud iam roles create headhunterFunctionRole --project=headhunter-ai-0088 \
  --file=iam/function-role.yaml

# Assign minimal permissions
gcloud projects add-iam-policy-binding headhunter-ai-0088 \
  --member=serviceAccount:headhunter-ai-0088@appspot.gserviceaccount.com \
  --role=projects/headhunter-ai-0088/roles/headhunterFunctionRole
```

Create `iam/function-role.yaml`:
```yaml
title: "Headhunter Function Role"
description: "Minimal permissions for Headhunter Cloud Functions"
stage: "GA"
includedPermissions:
  - firestore.documents.create
  - firestore.documents.delete
  - firestore.documents.get
  - firestore.documents.list
  - firestore.documents.update
  - storage.objects.create
  - storage.objects.delete
  - storage.objects.get
  - storage.objects.list
```

### API Keys Restrictions
```bash
# Restrict Firebase API key
gcloud services api-keys update API_KEY_ID \
  --allowed-referrers="https://headhunter-ai-0088.web.app/*,https://yourdomain.com/*" \
  --allowed-apis="firebase.googleapis.com,firebaseremoteconfig.googleapis.com"
```

### Content Security Policy
Add to React app's `public/index.html`:
```html
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  script-src 'self' 'unsafe-inline' https://*.googleapis.com https://*.firebase.com;
  style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
  font-src 'self' https://fonts.gstatic.com;
  img-src 'self' data: https://*.googleapis.com;
  connect-src 'self' https://*.googleapis.com https://*.firebase.com wss://*.firebase.com;
">
```

## 🚀 Step 9: Performance Optimization

### Cloud Functions Optimization
```json
// functions/package.json - production dependencies only
{
  "dependencies": {
    "firebase-admin": "^12.6.0",
    "firebase-functions": "^6.1.1",
    "zod": "^3.22.4"
  }
}
```

### Firestore Optimization
```javascript
// Use batch writes for bulk operations
const batchWrite = (docs, collection) => {
  const batch = db.batch();
  docs.forEach(doc => {
    const ref = db.collection(collection).doc();
    batch.set(ref, doc);
  });
  return batch.commit();
};

// Enable offline persistence in client
import { enableIndexedDbPersistence } from 'firebase/firestore';
enableIndexedDbPersistence(db);
```

### Caching Strategy
```javascript
// functions/src/cache.ts
import NodeCache from 'node-cache';

const cache = new NodeCache({ stdTTL: 300 }); // 5 minute TTL

export const withCache = (key: string, fn: () => Promise<any>) => {
  return async (...args: any[]) => {
    const cacheKey = `${key}_${JSON.stringify(args)}`;
    
    const cached = cache.get(cacheKey);
    if (cached) return cached;
    
    const result = await fn(...args);
    cache.set(cacheKey, result);
    return result;
  };
};
```

## 📊 Step 10: Backup & Recovery

### Automated Backups
```bash
# Create backup bucket
gsutil mb gs://headhunter-ai-0088-backups

# Set up scheduled exports
gcloud firestore export gs://headhunter-ai-0088-backups/$(date +%Y-%m-%d)
```

### Backup Function
```javascript
// functions/src/backup.ts
import { onSchedule } from "firebase-functions/v2/scheduler";
import { getFirestore } from "firebase-admin/firestore";

export const scheduledFirestoreExport = onSchedule(
  {
    schedule: "0 2 * * *", // Daily at 2 AM
    timeZone: "UTC",
    memory: "1GiB"
  },
  async (event) => {
    const bucket = 'gs://headhunter-ai-0088-backups';
    const timestamp = new Date().toISOString().split('T')[0];
    
    await getFirestore().export({
      collectionIds: ['candidates', 'jobs', 'users', 'organizations'],
      outputUriPrefix: `${bucket}/${timestamp}`
    });
    
    console.log(`Backup completed: ${bucket}/${timestamp}`);
  }
);
```

## 🔄 Step 11: CI/CD Pipeline

### GitHub Actions Workflow
Create `.github/workflows/deploy.yml`:
```yaml
name: Deploy to Firebase

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install Functions Dependencies
        run: cd functions && npm ci
      
      - name: Run Functions Tests
        run: cd functions && npm test
      
      - name: Install UI Dependencies
        run: cd headhunter-ui && npm ci
      
      - name: Run UI Tests
        run: cd headhunter-ui && npm test -- --coverage --watchAll=false

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install Dependencies
        run: |
          cd functions && npm ci
          cd ../headhunter-ui && npm ci
      
      - name: Build Functions
        run: cd functions && npm run build
      
      - name: Build UI
        run: cd headhunter-ui && npm run build
      
      - name: Deploy to Firebase
        uses: FirebaseExtended/action-hosting-deploy@v0
        with:
          repoToken: '${{ secrets.GITHUB_TOKEN }}'
          firebaseServiceAccount: '${{ secrets.FIREBASE_SERVICE_ACCOUNT }}'
          projectId: headhunter-ai-0088
```

## ✅ Step 12: Production Checklist

### Pre-deployment Checklist
- [ ] Security rules tested and deployed
- [ ] Database indexes created
- [ ] Environment variables configured
- [ ] API keys restricted
- [ ] Monitoring and alerting set up
- [ ] Backup strategy implemented
- [ ] Performance optimization applied
- [ ] Error handling tested
- [ ] Load testing completed
- [ ] Documentation updated

### Post-deployment Verification
- [ ] Health check endpoint responding
- [ ] Authentication working
- [ ] CRUD operations functional
- [ ] File upload pipeline working
- [ ] Search functionality operational
- [ ] Real-time updates working
- [ ] Mobile responsiveness verified
- [ ] Cross-browser compatibility tested

### Monitoring Dashboard URLs
- **Cloud Console**: https://console.cloud.google.com/home/dashboard?project=headhunter-ai-0088
- **Firebase Console**: https://console.firebase.google.com/project/headhunter-ai-0088
- **Functions Logs**: https://console.cloud.google.com/functions/list?project=headhunter-ai-0088
- **Firestore Console**: https://console.firebase.google.com/project/headhunter-ai-0088/firestore
- **Storage Console**: https://console.firebase.google.com/project/headhunter-ai-0088/storage

## 🆘 Troubleshooting

### Common Issues

1. **Function Timeout**
   ```bash
   # Increase timeout in function configuration
   firebase functions:config:set functions.timeout=540
   ```

2. **Firestore Permission Denied**
   ```bash
   # Check security rules
   firebase firestore:rules:list
   firebase firestore:rules:get --ruleset-id=RULESET_ID
   ```

3. **Storage Upload Fails**
   ```bash
   # Check CORS configuration
   gsutil cors get gs://headhunter-ai-0088-files
   gsutil cors set storage-cors.json gs://headhunter-ai-0088-files
   ```

4. **High Cloud Function Costs**
   - Implement request caching
   - Optimize cold start times
   - Use appropriate memory allocation
   - Monitor invocation patterns

### Support Contacts
- **Technical Issues**: Review logs in Cloud Console
- **Billing Issues**: Check usage in Firebase Console
- **Security Concerns**: Review IAM and security rules
- **Performance Issues**: Check monitoring dashboards

This deployment guide ensures a secure, scalable, and maintainable production deployment of Headhunter AI with comprehensive monitoring and backup strategies.