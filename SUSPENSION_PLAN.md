# Project Suspension & Cost Optimization Plan

**Date**: 2025-11-14
**Duration**: 1 week suspension
**Estimated Cost Savings**: ~$150-200/week

## Current Monthly Costs (Estimated)

| Resource | Monthly Cost | Weekly Cost | Notes |
|----------|-------------|-------------|-------|
| Cloud SQL (db-custom-2-7680, ALWAYS) | ~$400-600 | ~$100-150 | Biggest cost driver |
| Redis Memorystore (STANDARD_HA) | ~$200-280 | ~$50-70 | High availability tier |
| Cloud Run (8 Fastify services) | ~$20-40 | ~$5-10 | Pay per request |
| Cloud Run (40+ legacy functions) | ~$10-20 | ~$3-5 | Minimal usage |
| Firestore | ~$10-20 | ~$3-5 | Storage only |
| Cloud Storage | ~$5-10 | ~$1-3 | Container images + data |
| **TOTAL** | **~$645-970** | **~$162-243** | |

## Cost Optimization Strategy

### Phase 1: Immediate Shutdown (Save ~85% of costs)

**Execute these commands to minimize costs:**

```bash
# Set project context
gcloud config set project headhunter-ai-0088

# 1. STOP Cloud SQL (saves ~$100-150/week)
gcloud sql instances patch sql-hh-core \
  --activation-policy=NEVER \
  --quiet

# Verify it stopped
gcloud sql instances describe sql-hh-core --format="get(state)"
# Should show: RUNNABLE (stopped state)

# 2. DELETE Redis Instance (saves ~$50-70/week)
# NOTE: Cache data will be lost, but it's just a cache
gcloud redis instances delete redis-skills-us-central1 \
  --region=us-central1 \
  --quiet

# 3. Scale down Cloud Run services to zero minimum instances
# (They'll still respond to requests but won't have always-on instances)
for service in hh-embed-svc-production hh-search-svc-production hh-rerank-svc-production hh-evidence-svc-production hh-eco-svc-production hh-msgs-svc-production hh-admin-svc-production hh-enrich-svc-production; do
  gcloud run services update $service \
    --region=us-central1 \
    --min-instances=0 \
    --quiet
  echo "✅ Scaled down $service"
done

# 4. Optionally delete legacy Cloud Functions (saves ~$3-5/week)
# Only if you're certain they're not needed
# gcloud functions delete [function-name] --region=us-central1 --quiet
```

### Phase 2: Data Backup (Before Suspension)

```bash
# 1. Backup Firestore data (if needed)
gcloud firestore export gs://headhunter-ai-0088.appspot.com/firestore-backup-$(date +%Y%m%d) \
  --project=headhunter-ai-0088

# 2. Cloud SQL is automatically backed up daily
# Verify latest backup exists
gcloud sql backups list --instance=sql-hh-core --project=headhunter-ai-0088 --limit=5

# 3. Export critical configuration
gcloud run services describe hh-search-svc-production \
  --region=us-central1 \
  --format=yaml > /tmp/hh-search-svc-config-backup.yaml
```

### Phase 3: Document Current State

**Services Status Before Suspension:**
- **Cloud SQL**: db-custom-2-7680, ALWAYS policy, ~29K candidate embeddings
- **Redis**: STANDARD_HA, redis-skills-us-central1
- **Fastify Services**: 8 services, all healthy
- **Firestore**: ~29K candidate profiles
- **API Gateway**: Production gateway active

## Restart Procedure (After 1 Week)

### Quick Start (5-10 minutes)

```bash
# Set project
gcloud config set project headhunter-ai-0088

# 1. START Cloud SQL
gcloud sql instances patch sql-hh-core \
  --activation-policy=ALWAYS \
  --quiet

# Wait for Cloud SQL to become ready (~2-3 minutes)
echo "Waiting for Cloud SQL to start..."
while [ "$(gcloud sql instances describe sql-hh-core --format='get(state)')" != "RUNNABLE" ]; do
  echo -n "."
  sleep 10
done
echo "✅ Cloud SQL is ready"

# 2. RECREATE Redis Instance
gcloud redis instances create redis-skills-us-central1 \
  --size=5 \
  --region=us-central1 \
  --tier=standard-ha \
  --redis-version=redis_7_0 \
  --network=projects/headhunter-ai-0088/global/networks/default \
  --quiet

# Wait for Redis to become ready (~5-10 minutes)
echo "Waiting for Redis to be ready..."
while [ "$(gcloud redis instances describe redis-skills-us-central1 --region=us-central1 --format='get(state)')" != "READY" ]; do
  echo -n "."
  sleep 15
done
echo "✅ Redis is ready"

# Get Redis connection details
REDIS_HOST=$(gcloud redis instances describe redis-skills-us-central1 \
  --region=us-central1 --format='get(host)')
REDIS_PORT=$(gcloud redis instances describe redis-skills-us-central1 \
  --region=us-central1 --format='get(port)')
echo "Redis endpoint: $REDIS_HOST:$REDIS_PORT"

# 3. Update Cloud Run services with new Redis endpoint (if needed)
# Services should auto-reconnect, but update if Redis IP changed

# 4. Scale up Cloud Run services (optional - they auto-scale from 0)
for service in hh-search-svc-production hh-rerank-svc-production; do
  gcloud run services update $service \
    --region=us-central1 \
    --min-instances=1 \
    --quiet
  echo "✅ Scaled up $service"
done

# 5. Verify services are healthy
echo "Checking service health..."
curl -sf https://hh-search-svc-production-akcoqbr7sa-uc.a.run.app/health
curl -sf https://hh-rerank-svc-production-akcoqbr7sa-uc.a.run.app/health

echo "✅ All services restarted successfully"
```

### Detailed Validation

```bash
# Test hybrid search end-to-end
SEARCH_API_KEY=$(gcloud secrets versions access latest --secret=api-gateway-key --project=headhunter-ai-0088)

curl -H "x-api-key: $SEARCH_API_KEY" \
     -H "X-Tenant-ID: tenant-alpha" \
     -H "Content-Type: application/json" \
     https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/search/hybrid \
     -d '{
       "jobDescription": "Senior Software Engineer with Python and AWS experience",
       "limit": 5,
       "includeDebug": true
     }'

# Expected: HTTP 200, results array, metadata showing Gemini rerank
```

## Important Notes

### Data Persistence
- **Firestore**: Data persists (only pay for storage ~$0.18/GB/month)
- **Cloud SQL**: Data persists even when stopped (backups retained)
- **Redis**: Data will be LOST when deleted (it's cache, can be regenerated)
- **Cloud Storage**: Container images and files persist

### Cost During Suspension
- **With Cloud SQL stopped + Redis deleted**: ~$20-40/week
- **Without optimization**: ~$162-243/week
- **Savings**: ~$120-200/week (~85% reduction)

### Risks
1. **Redis data loss**: Cache needs rebuilding (rerank scores, embeddings cache)
2. **Cold start latency**: First requests after restart will be slower
3. **Configuration drift**: Ensure no manual changes during suspension

### Alternative: Lighter Shutdown

If you want to keep Redis for faster restart:

```bash
# Stop only Cloud SQL (saves ~$100-150/week, ~65% reduction)
gcloud sql instances patch sql-hh-core --activation-policy=NEVER --quiet

# Keep Redis running for instant restart
# Total cost during suspension: ~$70-90/week
```

## Quick Reference

**Stop Everything:**
```bash
./scripts/suspend-project.sh  # If script exists
# OR manually execute Phase 1 commands above
```

**Restart Everything:**
```bash
./scripts/restart-project.sh  # If script exists
# OR manually execute "Restart Procedure" above
```

**Check Status:**
```bash
# Cloud SQL
gcloud sql instances describe sql-hh-core --format="get(state,settings.activationPolicy)"

# Redis
gcloud redis instances describe redis-skills-us-central1 --region=us-central1 --format="get(state)" 2>/dev/null || echo "Redis not found (deleted)"

# Cloud Run services
gcloud run services list --project=headhunter-ai-0088 --format="table(name,status.conditions[0].status)" | grep hh-
```

## Support

If you encounter issues during restart:
1. Check Cloud Console: https://console.cloud.google.com/run?project=headhunter-ai-0088
2. Review logs: `gcloud logging read "resource.type=cloud_run_revision" --limit=50`
3. Consult HANDOVER.md for detailed troubleshooting
