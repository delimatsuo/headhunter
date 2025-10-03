# Comprehensive Production Smoke Test

## Overview

The `comprehensive_smoke_test.sh` script performs end-to-end testing of all 8 Headhunter services through the API Gateway in production.

## Quick Start

```bash
# Run with defaults (fetches API key from Secret Manager)
./scripts/comprehensive_smoke_test.sh

# Run with custom configuration
./scripts/comprehensive_smoke_test.sh \
  --project-id headhunter-ai-0088 \
  --gateway-url https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev \
  --tenant-id test-tenant

# Run with explicit API key (bypass Secret Manager)
./scripts/comprehensive_smoke_test.sh --api-key "your-api-key-here"

# Enable verbose output for debugging
./scripts/comprehensive_smoke_test.sh --verbose
```

## Services Tested

| Service | Port | Endpoints Tested | Tests |
|---------|------|------------------|-------|
| **hh-admin-svc** | 7107 | `/admin/health`, `/admin/snapshots`, `/admin/policies` | 3 |
| **hh-embed-svc** | 7101 | `/v1/embeddings/generate`, `/v1/embeddings/batch` | 3 |
| **hh-search-svc** | 7102 | `/v1/search`, `/v1/search/hybrid`, `/v1/search/candidates/:id` | 4 |
| **hh-rerank-svc** | 7103 | `/v1/rerank`, `/v1/rerank/metrics` | 3 |
| **hh-msgs-svc** | 7106 | `/v1/skills/expand`, `/v1/msgs/notify` | 3 |
| **hh-evidence-svc** | 7104 | `/v1/evidence/candidates/:id`, `/v1/evidence/provenance/:id`, `/v1/evidence/audit` | 4 |
| **hh-eco-svc** | 7105 | `/v1/eco/validate`, `/v1/eco/occupations`, `/v1/eco/normalize`, `/v1/eco/templates` | 5 |
| **hh-enrich-svc** | 7108 | `/v1/enrich/profile`, `/v1/enrich/status/:id`, `/v1/enrich/batch` | 4 |
| **Integration** | N/A | Full search pipeline (embed → search → rerank → evidence) | 1 |

**Total: 32 tests**

## Test Categories

### 1. Gateway Health Checks
- Gateway root health endpoint
- Gateway readiness endpoint

### 2. Service Health Checks
- Individual health endpoint for each of the 8 services

### 3. Functional Tests
- Actual API operations with realistic payloads
- Tests use the 6 test candidates loaded in Firestore:
  - sarah_chen
  - marcus_rodriguez
  - james_thompson
  - lisa_park
  - emily_watson
  - john_smith

### 4. Integration Test
- End-to-end search pipeline:
  1. Generate embedding for job description
  2. Perform semantic search
  3. Rerank top candidates
  4. Fetch evidence for top match

## Requirements

### Dependencies
- `curl` - HTTP client
- `jq` - JSON processor
- `gcloud` - Google Cloud CLI (if fetching API key from Secret Manager)
- `python3` - For timing calculations

### Authentication
- **Option 1**: Script fetches API key from Secret Manager (requires gcloud auth)
- **Option 2**: Provide API key via `--api-key` flag

### GCP Permissions
If using Secret Manager (default):
- `secretmanager.versions.access` on secret `api-gateway-key`

## Output

### Success Example
```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🚀 Headhunter Production Smoke Test Suite 🚀         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

ℹ Project ID:    headhunter-ai-0088
ℹ Gateway URL:   https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev
ℹ Tenant ID:     test-tenant

🔑 Retrieving API key from Secret Manager...
✅ API key retrieved successfully

🏁 Starting comprehensive smoke tests...

═══════════════════════════════════════════════════════════
  🏥 Gateway Health Checks
═══════════════════════════════════════════════════════════
⏳ Test 1: Gateway root health... ✅ PASS (HTTP 200, 145ms)
⏳ Test 2: Gateway readiness... ✅ PASS (HTTP 200, 132ms)

[... more tests ...]

═══════════════════════════════════════════════════════════
  📊 Test Results Summary
═══════════════════════════════════════════════════════════

  Total tests run:    32
  ✅ Passed:         32
  ❌ Failed:         0
  ⏭  Skipped:        0
  Pass rate:         100.0%

═══════════════════════════════════════════════════════════
  🎉 ALL TESTS PASSED! Production deployment is healthy.
═══════════════════════════════════════════════════════════
```

### Failure Example
```
⏳ Test 15: Rerank candidates... ❌ FAIL (Expected 200, got 500, 234ms)

[... more tests ...]

═══════════════════════════════════════════════════════════
  ❌ SOME TESTS FAILED. Please investigate the failures.
═══════════════════════════════════════════════════════════

Failed tests:
  • Rerank candidates (status_mismatch|234|expected_200_got_500)
  • Search candidates (curl_error|156)
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All tests passed |
| 1 | One or more tests failed |
| 2 | Configuration error (missing dependencies, invalid parameters, etc.) |

## Verbose Mode

Enable verbose output to see response previews and detailed execution:

```bash
./scripts/comprehensive_smoke_test.sh --verbose
```

Verbose mode shows:
- API key retrieval details
- Response body previews (first 200 chars)
- Detailed curl execution logs
- Additional diagnostic information

## Troubleshooting

### "Failed to retrieve API key from Secret Manager"
**Solution**: Ensure you're authenticated with gcloud and have access to the secret:
```bash
gcloud auth application-default login
gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088
```

Or provide API key directly:
```bash
export API_KEY="your-key-here"
./scripts/comprehensive_smoke_test.sh --api-key "$API_KEY"
```

### "Missing required dependencies"
**Solution**: Install required tools:
```bash
# macOS
brew install curl jq python3

# Ubuntu/Debian
sudo apt-get install curl jq python3
```

### Tests timing out
**Solution**: Check network connectivity and gateway status:
```bash
curl -I https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/health
```

### 401 Unauthorized errors
**Solution**: Verify API key is valid:
```bash
# Check secret value
gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088

# Test manually
curl -H "X-API-Key: YOUR_KEY" \
  https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/health
```

## Integration with CI/CD

### GitHub Actions
```yaml
- name: Run smoke tests
  run: |
    ./scripts/comprehensive_smoke_test.sh \
      --api-key "${{ secrets.API_GATEWAY_KEY }}" \
      --tenant-id "ci-test-tenant"
```

### Cloud Build
```yaml
- name: 'gcr.io/cloud-builders/gcloud'
  entrypoint: 'bash'
  args:
    - '-c'
    - |
      ./scripts/comprehensive_smoke_test.sh \
        --project-id $PROJECT_ID \
        --gateway-url ${_GATEWAY_URL}
```

## Related Scripts

- `scripts/smoke-test-deployment.sh` - Deployment-specific smoke tests with more extensive coverage
- `scripts/smoke_test_production.sh` - Simpler production smoke test (fewer tests)
- `scripts/test_gateway_end_to_end.sh` - Gateway-specific end-to-end tests
- `scripts/run-post-deployment-load-tests.sh` - Load testing suite

## Contributing

When adding new services or endpoints:

1. Add test function following the pattern: `test_<service>_service()`
2. Update service count in header comments
3. Add service to the "Services Tested" table in this README
4. Call the test function in `main()`
5. Update total test count

## Support

For issues or questions:
- Check `docs/HANDOVER.md` for operational runbooks
- Review `docs/PRODUCTION_DEPLOYMENT_GUIDE.md` for deployment context
- See `ARCHITECTURE.md` for service architecture details
