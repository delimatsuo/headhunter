# HeadHunter Deep Infrastructure Security Audit

**Date:** January 8, 2026
**Auditor:** Claude Code (Senior Security Analyst)
**Scope:** Cloud Infrastructure, Databases, Networking, Secrets Management
**Project:** headhunter-ai-0088

---

## Executive Summary

This deep security audit covers the cloud infrastructure, databases, and networking components of the HeadHunter recruitment platform. The audit examines GCP services including Cloud Run, Cloud SQL, Memorystore (Redis), Firestore, Secret Manager, VPC configuration, and IAM permissions.

### Overall Risk Assessment

| Category | Status | Risk Level |
|----------|--------|------------|
| Cloud Run Security | Good with improvements needed | MEDIUM |
| Firebase/Firestore | Well-configured | LOW |
| PostgreSQL Security | Needs production hardening | HIGH |
| Redis Security | Needs production hardening | MEDIUM |
| Secret Management | Good | LOW |
| Network/VPC | Good | LOW |
| IAM Permissions | Well-configured | LOW |
| API Gateway | Good | LOW |
| Encryption | Needs explicit configuration | MEDIUM |

---

## 1. Cloud Run Security

### Positive Findings

1. **Dockerfile Security Best Practices**
   - Non-root user (`headhunter`) configured
   - Multi-stage builds (no dev tools in production image)
   - Health checks configured
   - `NODE_ENV=production` set
   - Minimal base image (`node:20-slim`)

2. **Service Configuration**
   - `run.googleapis.com/ingress: internal-and-cloud-load-balancing` restricts public access
   - Service accounts configured per service
   - CPU throttling disabled for consistent performance

### Issues Identified

#### HIGH: CloudBuild Missing Security Flags
**Location:** `services/hh-search-svc-cloudbuild.yaml`

```yaml
# Current (INSECURE):
- 'gcloud run deploy hh-search-svc-production ...'

# Missing critical flags:
#   --no-allow-unauthenticated
#   --service-account=<service-account>
#   --vpc-connector=<connector>
#   --memory=<limit>
#   --cpu=<limit>
```

**Recommendation:** Add security flags to all CloudBuild configurations:
```yaml
args:
  - 'run'
  - 'deploy'
  - 'hh-search-svc-production'
  - '--image=...'
  - '--region=us-central1'
  - '--platform=managed'
  - '--no-allow-unauthenticated'  # REQUIRED
  - '--service-account=search-production@headhunter-ai-0088.iam.gserviceaccount.com'
  - '--vpc-connector=svpc-us-central1'
  - '--memory=2Gi'
  - '--cpu=2'
  - '--set-secrets=PGVECTOR_PASSWORD=db-primary-password:latest'
```

---

## 2. Firebase/Firestore Security

### Positive Findings

1. **Excellent Security Rules**
   - Authentication required for all operations
   - Organization-based access control (`isOrgMember()`)
   - Role-based permissions (recruiter, admin, super_admin)
   - Default deny rule at the end
   - Write operations disabled for client (Cloud Functions only)
   - Audit logs protected (admin-only access)

2. **Storage Rules**
   - Authentication required
   - File size limits (10MB)
   - Default deny rule

### Minor Concerns

#### LOW: Domain-Based Access Control
**Location:** `firestore.rules:49-51`

```javascript
getUserEmail().matches('.*@ella.com.br') ||
getUserEmail().matches('.*@ellaexecutivesearch.com')
```

**Note:** This relies on Firebase Auth properly validating email domains. If using email/password auth with unverified emails, this could be bypassed.

**Recommendation:** Ensure email verification is required, or use Google Workspace SSO for domain-based access.

---

## 3. PostgreSQL Database Security

### Issues Identified

#### HIGH: SSL Disabled in Development and Some Configurations
**Location:** Multiple files

```yaml
# functions/.env.yaml
PGVECTOR_SSL_MODE: disable

# functions/src/file-upload-pipeline.ts
process.env.PGVECTOR_SSL_MODE = "disable";

# docker-compose.local.yml (development only - acceptable)
```

**Risk:** Data in transit is not encrypted, allowing potential interception.

**Recommendation:**
1. **Production:** Always set `PGVECTOR_SSL_MODE=require`
2. **Cloud SQL:** Enable SSL certificates and require them
3. Add validation to prevent startup with `ssl=disable` in production:

```typescript
if (process.env.NODE_ENV === 'production' && process.env.PGVECTOR_SSL_MODE !== 'require') {
  throw new Error('SSL must be enabled in production');
}
```

#### MEDIUM: Weak Development Passwords
**Location:** `docker-compose.local.yml:12`

```yaml
POSTGRES_PASSWORD: headhunter
```

**Note:** This is acceptable for local development but ensure:
- Production uses Secret Manager with strong passwords
- Development credentials never deployed to production
- `.env.local` files are in `.gitignore`

### Positive Findings

- Cloud SQL configured with Private IP (VPC peering)
- Database users managed via Secret Manager
- Application users with least privilege (not superuser)

---

## 4. Redis Security

### Issues Identified

#### MEDIUM: TLS Disabled by Default
**Location:** `services/hh-search-svc/src/config.ts:176-178`

```typescript
tls: parseBoolean(process.env.REDIS_TLS, false),  // Default: false
tlsRejectUnauthorized: parseBoolean(process.env.REDIS_TLS_REJECT_UNAUTHORIZED, true),
caCert: process.env.REDIS_TLS_CA,
```

**Risk:** Redis traffic unencrypted if `REDIS_TLS` not explicitly set.

**Recommendation:**
1. **Production:** Set `REDIS_TLS=true` for all services
2. Memorystore Enterprise supports TLS - enable it
3. Add production validation:

```typescript
if (process.env.NODE_ENV === 'production' && process.env.REDIS_TLS !== 'true') {
  console.warn('WARNING: Redis TLS disabled in production');
}
```

#### LOW: No Redis Password in Local Development
**Location:** `docker-compose.local.yml:27`

```yaml
command: ['redis-server', '--save', '', '--appendonly', 'no', ...]
# No --requirepass flag
```

**Note:** Acceptable for local development. Production Memorystore handles authentication via IAM.

### Positive Findings

- Redis data is ephemeral (no persistence in local dev)
- `allkeys-lru` eviction policy prevents memory exhaustion
- Production uses Memorystore with VPC isolation

---

## 5. Secret Management

### Positive Findings

1. **Secret Manager Integration**
   - API keys stored in Secret Manager
   - Secrets accessed via `gcloud secrets versions access`
   - Service accounts have `roles/secretmanager.secretAccessor`
   - OAuth credentials managed via Secret Manager

2. **Good Practices Observed**
   ```bash
   # Secrets created properly:
   gcloud secrets create together-ai-credentials --project=$PROJECT_ID

   # IAM binding for access:
   gcloud secrets add-iam-policy-binding together-ai-credentials \
     --member="serviceAccount:..." \
     --role="roles/secretmanager.secretAccessor"
   ```

3. **Secret Rotation Awareness**
   - Template mentions rotation: `SECRET_ROTATION_OVERRIDE_db-primary-password`

### Recommendations

1. **Implement Secret Rotation Policy**
   - Configure automatic rotation for database passwords
   - Set up alerts for secrets approaching expiration

2. **Audit Secret Access**
   - Enable Cloud Audit Logs for Secret Manager
   - Monitor for unusual access patterns

---

## 6. Network and VPC Configuration

### Positive Findings

1. **VPC Connector Configured**
   - `svpc-us-central1` connector for Cloud Run
   - Private IP connectivity to Cloud SQL and Redis
   - `private-ranges-only` egress setting

2. **Network Isolation**
   - Cloud SQL uses private IP (no public IP)
   - Memorystore in VPC
   - Firestore accessed via Google's internal network

3. **Documentation**
   - VPC configuration well-documented in `docs/HANDOVER.md`
   - Troubleshooting guides for connectivity issues

### Recommendations

1. **Enable VPC Flow Logs** for security monitoring
2. **Configure Cloud Armor** for DDoS protection at the load balancer
3. **Review Firewall Rules** periodically

---

## 7. IAM Permissions

### Positive Findings

1. **Least Privilege Implementation**
   ```bash
   # Per-service IAM roles:
   hh-search-svc: roles/cloudsql.client, roles/redis.viewer, roles/secretmanager.secretAccessor
   hh-embed-svc: roles/cloudsql.client, roles/redis.viewer, roles/aiplatform.user, roles/secretmanager.secretAccessor
   hh-enrich-svc: roles/cloudsql.client, roles/datastore.user, roles/pubsub.publisher, roles/pubsub.subscriber
   ```

2. **Service-to-Service Authentication**
   - Cloud Run invoker bindings configured
   - Gateway service account for API Gateway integration

3. **Audit Logging**
   ```bash
   gcloud logging sinks create "hh-audit-${ENVIRONMENT}" \
     "storage.googleapis.com/headhunter-audit-${ENVIRONMENT}" \
     --log-filter='resource.type="cloud_run_revision"'
   ```

### Recommendations

1. **Periodic IAM Review**
   - Schedule quarterly reviews of IAM bindings
   - Remove unused service accounts

2. **Enable Organization Policy Constraints**
   - Restrict public Cloud Run services
   - Require VPC connectors for all services

---

## 8. API Gateway Security

### Positive Findings

1. **Authentication Flow**
   - OAuth 2.0 client credentials flow
   - JWT token validation
   - Tenant ID header validation (`X-Tenant-ID`)

2. **Gateway Validation Script**
   - Tests authentication
   - Validates routing
   - Load testing with k6

### Recommendations

1. **Rate Limiting at Gateway Level**
   - Configure Cloud Endpoints/Apigee rate limits
   - Per-tenant quotas

2. **Enable Cloud Armor**
   - WAF rules for common attacks
   - Bot protection

---

## 9. Encryption

### Current State

| Data Type | At Rest | In Transit |
|-----------|---------|------------|
| Firestore | Google-managed | TLS (automatic) |
| Cloud SQL | Google-managed | Configurable |
| Redis | Google-managed | Configurable |
| Storage | Google-managed | TLS (automatic) |
| Secrets | Google-managed | TLS (automatic) |

### Issues

#### MEDIUM: No CMEK (Customer-Managed Encryption Keys)
All encryption uses Google-managed keys. For compliance requirements, consider CMEK.

**Recommendation:** If required by compliance:
```bash
# Create KMS key ring
gcloud kms keyrings create headhunter-keyring --location=us-central1

# Create encryption key
gcloud kms keys create headhunter-db-key \
  --keyring=headhunter-keyring \
  --location=us-central1 \
  --purpose=encryption

# Apply to Cloud SQL
gcloud sql instances patch hh-prod-sql \
  --disk-encryption-key=projects/headhunter-ai-0088/locations/us-central1/keyRings/headhunter-keyring/cryptoKeys/headhunter-db-key
```

---

## 10. Action Items

### Immediate (This Week)

| Priority | Issue | Action |
|----------|-------|--------|
| HIGH | CloudBuild security flags | Add `--no-allow-unauthenticated`, service accounts, VPC connector |
| HIGH | PostgreSQL SSL | Set `PGVECTOR_SSL_MODE=require` in production |
| MEDIUM | Redis TLS | Set `REDIS_TLS=true` in production |

### Short-term (Next 2 Weeks)

| Priority | Issue | Action |
|----------|-------|--------|
| MEDIUM | Production validation | Add startup checks for SSL/TLS in production |
| MEDIUM | Cloud Armor | Enable WAF at load balancer |
| LOW | Secret rotation | Implement rotation policy |

### Medium-term (Next Month)

| Priority | Issue | Action |
|----------|-------|--------|
| LOW | CMEK | Evaluate need for customer-managed keys |
| LOW | VPC Flow Logs | Enable for security monitoring |
| LOW | IAM Review | Schedule quarterly IAM audits |

---

## Appendix: Security Checklist

### Production Deployment Checklist

- [ ] `PGVECTOR_SSL_MODE=require` set
- [ ] `REDIS_TLS=true` set
- [ ] `--no-allow-unauthenticated` on all Cloud Run services
- [ ] Service accounts assigned to all services
- [ ] VPC connector configured for all services
- [ ] Secrets in Secret Manager (no hardcoded credentials)
- [ ] Audit logging enabled
- [ ] Cloud Armor enabled (if applicable)

### Files Reviewed

- `services/hh-*-svc-cloudbuild.yaml` (8 files)
- `services/hh-*/Dockerfile` (9 files)
- `services/hh-enrich-svc/python_runtime/scripts/setup_service_iam.sh`
- `services/hh-enrich-svc/python_runtime/cloud_run_worker/cloud-run.yaml`
- `firestore.rules`
- `storage.rules`
- `docker-compose.local.yml`
- `services/*/src/config.ts` (service configurations)
- Deployment scripts in `scripts/` and `services/hh-enrich-svc/python_runtime/scripts/`

---

*Report generated by Claude Code Deep Security Audit*
