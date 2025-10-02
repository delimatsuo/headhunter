# Cloud Run Deployment Troubleshooting Summary
**Date**: October 2, 2025  
**Duration**: 5+ hours  
**Status**: Unresolved - Services cannot initialize

## Root Cause
**Services fail to start due to blocking I/O operations during bootstrap**

All 8 services timeout during deployment because they perform blocking network operations (database, Redis, Pub/Sub connections) BEFORE the HTTP server starts listening on port 8080. Cloud Run's startup probe times out waiting for port 8080 to become available.

## Key Findings

### 1. Network Configuration (Fixed)
- ✅ VPC peering configured correctly
- ✅ Firewall rules updated to allow Cloud SQL range (10.159.0.0/16)
- ✅ Redis connection details corrected (10.159.1.4:6378)
- ✅ VPC egress set to `all-traffic`

### 2. Service Configuration (Fixed)
- ✅ Container port: 8080 (correct)
- ✅ Database ports: 5432 for Postgres, 6378 for Redis
- ✅ IAM permissions: gateway SA has run.invoker role

### 3. Bootstrap Problem (Unfixed)
**Issue**: Services initialize dependencies BEFORE calling `server.listen()`

Examples:
- `hh-admin-svc`: Creates Pub/Sub, Jobs, Monitoring clients at lines 18-22
- `hh-embed-svc`: Has lazy init but Cloud SQL still times out in background
- `hh-evidence-svc`: Same pattern as embed-svc

**Result**: If any client initialization hangs (10s+), Cloud Run marks service as failed.

### 4. Ingress Restriction Discovery
Services are configured with `ingress: internal-and-cloud-load-balancing`, which prevents direct external access. This caused misleading 404 errors during testing.

When changed to `ingress: all`:
- Services return HTTP 503 (Service Unavailable)
- Confirms containers exist but aren't healthy

## Failed Approaches

1. ❌ Added database port configuration
2. ❌ Fixed Redis host/port
3. ❌ Updated VPC firewall rules
4. ❌ Changed VPC egress to all-traffic
5. ❌ Tested with unauthenticated access
6. ❌ Multiple redeployment attempts

None resolved the bootstrap timeout issue.

## Recommended Solutions

### Option 1: Lazy Initialization (Recommended)
**Refactor all services to:**
1. Call `server.listen()` FIRST
2. Register `/health` endpoint that returns "initializing" status
3. Initialize dependencies in `setImmediate()` callback
4. Handle initialization failures gracefully (retry logic)

**Example** (hh-embed-svc already follows this pattern):
```typescript
const server = await buildServer();
server.get('/health', () => ({ status: isReady ? 'ok' : 'initializing' }));
await server.listen({ port: 8080, host: '0.0.0.0' });

setImmediate(async () => {
  try {
    // Initialize database, Redis, etc.
    isReady = true;
  } catch (error) {
    // Log and retry
  }
});
```

### Option 2: Increase Startup Timeout
Add startup probe configuration to allow 2-3 minutes for initialization:
```yaml
spec:
  template:
    spec:
      containers:
        - startupProbe:
            tcpSocket:
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 12  # 30s + (10s * 12) = 150s total
```

### Option 3: Connection Pooling
Use connection pools that initialize lazily on first request rather than eagerly during bootstrap.

## Next Steps

1. **Refactor hh-admin-svc** to use lazy initialization pattern
2. **Verify hh-embed-svc** lazy init actually works (Cloud SQL still timing out)
3. **Add retry logic** for failed connections
4. **Consider health check grace period** to allow slow startups
5. **Test locally** with docker-compose to verify bootstrap succeeds

## Files Modified
- `config/cloud-run/*.yaml`: VPC egress, Redis config, database ports
- Firewall rule: `hh-allow-internal` updated with Cloud SQL range
- Multiple deployment attempts logged in `.deployment/`

## Commits
- 1526ec9: Add PGVECTOR_PORT environment variables
- 4d7e3a6: Enable all-traffic VPC egress
- 4333115: Fix Redis host and port
- 9a11adb: Add Cloud SQL peering range to firewall
