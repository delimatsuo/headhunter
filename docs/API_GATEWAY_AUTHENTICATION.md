# API Gateway Authentication

## ✅ Authentication Configured

### API Key Setup

**Location**: Stored securely in Google Cloud Secret Manager
**Secret Name**: `api-gateway-key`
**Project**: headhunter-ai-0088

To retrieve the API key for testing:
```bash
gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088
```

### API Gateway Configuration

- **Gateway URL**: https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev
- **Managed Service**: headhunter-api-gateway-production-300w3vetj4ih2.apigateway.headhunter-ai-0088.cloud.goog
- **Authentication**: API Key via query parameter or X-API-Key header

### Working Authentication Methods

#### 1. Health Endpoints (No Auth Required)
```bash
curl https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/health
```

**Response**:
```json
{"status":"ok","checks":{"pubsub":true,"jobs":true,"monitoring":{"healthy":true}}}
```

#### 2. API Key via Query Parameter
```bash
API_KEY=$(gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088)

curl -X POST "https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/embeddings/generate?key=${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"text": "Senior Python developer"}'
```

#### 3. API Key via Header
```bash
API_KEY=$(gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088)

curl -X POST https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/embeddings/generate \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"text": "Senior Python developer"}'
```

#### 4. Service Account JWT (Backend-to-Backend)
```bash
TOKEN=$(gcloud auth print-identity-token --audiences=https://hh-embed-svc-production-akcoqbr7sa-uc.a.run.app)

curl -X POST https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/embeddings/generate \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}'
```

## Security Best Practices

### ✅ Current Implementation
- API key stored in Secret Manager (not in code)
- Key restricted to specific API Gateway service
- Separate keys for development/production environments

### 🔒 Additional Security (Future Enhancements)
- [ ] Rotate API keys regularly (90 days recommended)
- [ ] Implement rate limiting per API key
- [ ] Add IP allowlisting for production keys
- [ ] Monitor API key usage via Cloud Monitoring
- [ ] Implement OAuth2 for user authentication

## Testing the Gateway

### Test Script
```bash
#!/bin/bash
# Retrieve API key from Secret Manager
export API_KEY=$(gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088)

# Test health endpoint (no auth)
echo "Testing health endpoint..."
curl -s https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/health | jq .

# Test embeddings endpoint (with auth)
echo -e "\nTesting embeddings endpoint..."
curl -s -X POST "https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/embeddings/generate?key=${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"text": "Senior Python developer"}' | jq .
```

## Next Steps for Production Testing

1. ✅ **Authentication Configured** - API key in Secret Manager
2. ⏳ **Load Test Data** - Need candidates in Firestore + embeddings in pgvector
3. ⏳ **Test Search Flow** - Verify end-to-end: JD → embeddings → pgvector → candidates
4. ⏳ **Verify Cache** - Ensure rerank cache is working (target: 98% hit rate)

## Production Readiness Status

✅ **Ready**:
- API Gateway deployed and accessible
- API key securely stored in Secret Manager
- Health endpoints responding correctly
- All backend services healthy

⏳ **Remaining Blockers**:
- No test data loaded (can't test search without candidates)
- No embeddings in pgvector (can't test semantic search)

---

**Last Updated**: October 3, 2025
**Security Review**: Pending
