# Security Audit Report - January 2026 (Final)

**Audit Date:** January 8, 2026
**Auditor:** Claude Code Security Analysis
**Scope:** Full application security audit including infrastructure, authentication, secrets, and code

---

## Executive Summary

The Headhunter application demonstrates a **strong security posture** with properly implemented authentication, authorization, rate limiting, and infrastructure controls. Previous audit findings have been remediated. A few low-to-medium risk items remain for consideration.

### Overall Security Rating: **A-** (Strong)

| Category | Rating | Notes |
|----------|--------|-------|
| Authentication & Authorization | A | Firebase + Gateway JWT, role-based access |
| Infrastructure Security | A | VPC isolation, no public auth, service accounts |
| Secrets Management | A- | Secret Manager used, one documentation issue |
| Input Validation | A | Schema validation, parameterized queries |
| Dependency Security | A | 0 npm vulnerabilities across all packages |
| Logging & Monitoring | A | Structured logs, no sensitive data exposure |
| CORS & Rate Limiting | A | Properly configured with tenant isolation |

---

## Detailed Findings

### 1. Authentication & Authorization ✅ SECURE

**Strengths:**
- Firebase Authentication with custom claims for roles
- API Gateway JWT verification with JWKS caching
- Token revocation checking (`checkRevoked: true` by default)
- Multi-issuer support for hybrid authentication
- Token caching with proper expiration
- Security warning emitted when `AUTH_MODE=none`

**Implementation:** `services/common/src/auth.ts`
- Lines 252-284: Proper JWT verification with Firebase and Gateway fallback
- Lines 286-305: User building with org_id validation
- Lines 307-342: Authentication plugin with health endpoint exclusion

**Firestore Rules:** `firestore.rules`
- Role-based access (admin, super_admin, recruiter)
- Organization-scoped data isolation
- Write operations restricted to Cloud Functions
- Default deny rule for unmatched paths

**Storage Rules:** `storage.rules`
- 10MB upload size limit
- User ownership validation
- Write operations restricted to Cloud Functions

### 2. Cloud Run Deployment Security ✅ SECURE

All 8 CloudBuild files properly configured:
- `--no-allow-unauthenticated` (requires authentication)
- Service-specific service accounts (least privilege)
- VPC connector with private egress
- Resource limits (CPU, memory, min/max instances)
- Secret Manager integration

**Files verified:**
- `hh-search-svc-cloudbuild.yaml`
- `hh-embed-svc-cloudbuild.yaml`
- `hh-rerank-svc-cloudbuild.yaml`
- `hh-enrich-svc-cloudbuild.yaml`
- `hh-evidence-svc-cloudbuild.yaml`
- `hh-eco-svc-cloudbuild.yaml`
- `hh-msgs-svc-cloudbuild.yaml`
- `hh-admin-svc-cloudbuild.yaml`

### 3. Injection Prevention ✅ SECURE

**SQL Injection Prevention:**
- Schema/table names validated against allowlist (`services/hh-embed-svc/src/config.ts:6-25`)
- Schema validation: `['search', 'public', 'test']`
- Table name pattern: `/^[a-z_][a-z0-9_]{0,62}$/`
- All query parameters use parameterized queries (`$1`, `$2`, etc.)
- Same validation in `services/hh-search-svc/src/config.ts`

**Command Injection Prevention:**
- No `eval()` or `new Function()` in application code
- No unsafe `exec`/`spawn` with user input
- `DOMPurify` used in UI for XSS prevention

### 4. Dependency Security ✅ SECURE

```
npm audit results:
├── /services: 0 vulnerabilities
├── /functions: 0 vulnerabilities
└── /headhunter-ui: 0 vulnerabilities (via npm overrides)
```

**UI package.json overrides applied:**
- `nth-check: ^2.1.1`
- `postcss: ^8.4.31`
- `svgo: ^3.0.0`
- `webpack-dev-server: ^5.2.1`

### 5. Secrets Management ⚠️ LOW RISK

**Properly Handled:**
- All production secrets in GCP Secret Manager
- `.gitignore` excludes all `.env`, `*.key`, `*.pem`, service account files
- CloudBuild uses `--set-secrets` for runtime injection
- Infrastructure config files contain only references, not values

**Finding: API Gateway Key in Documentation**
- **Risk Level:** LOW-MEDIUM
- **Location:** `docs/HANDOVER.md`, `docs/testing-readiness-report.md`, `scripts/validate_search_fix.py`
- **Key:** `AIzaSyD4fwoF0SMDVsA4A1Ip0_dT-qfP1OYPODs`
- **Mitigating Factors:**
  - Protected by API Gateway requiring authentication
  - Cloud Run services require IAM authentication
  - Key is tenant-specific, not a master key
- **Recommendation:** Rotate this key and update documentation to use `gcloud secrets versions access` commands instead of hardcoded values

**Firebase Web API Key (NOT a vulnerability):**
- `AIzaSyCPov0DTRn0HEalOlZ8UJUUmMZjnSne8IU` in `headhunter-ui/src/config/firebase.ts`
- Firebase Web API keys are designed to be public
- Security enforced through Firebase Security Rules (which are properly configured)

### 6. Rate Limiting ✅ SECURE

**Implementation:** `services/common/src/server.ts` and `services/common/src/rate_limit.ts`

**Features:**
- Global rate limit via `@fastify/rate-limit`
- Tenant-scoped rate limiting via Redis
- Route-specific limits (hybrid: 30 RPS, rerank: 10 RPS)
- Burst allowance configuration
- Proper `Retry-After` headers
- Rate limit headers in responses

### 7. CORS Configuration ✅ SECURE

**Implementation:** `services/common/src/config.ts:202-227`

**Allowed Origins:**
- `https://{projectId}.web.app`
- `https://{projectId}.firebaseapp.com`
- Localhost only in development mode
- Custom origins via `CORS_ALLOWED_ORIGINS` env var

### 8. Security Headers ✅ SECURE

**Implementation:** `services/common/src/server.ts:39`

Helmet.js enabled globally providing:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `X-XSS-Protection: 1; mode=block`
- Content Security Policy
- And other security headers

### 9. Logging Security ✅ SECURE

**Reviewed:** `services/common/src/auth.ts` logging patterns

**Good Practices:**
- Logs issuer names, not token values
- Error objects logged without sensitive payload
- Request IDs for correlation
- Structured JSON logging

**No sensitive data in logs:**
- No password logging
- No token content logging
- No API key logging

### 10. Infrastructure Security ✅ SECURE

**VPC Configuration:** `config/infrastructure/headhunter-ai-0088-production.env`
- VPC with dedicated subnets for Cloud Run, SQL, Redis
- VPC connector for private egress
- NAT gateway for outbound traffic

**Cloud SQL:**
- Private IP only (via VPC)
- Separate users per service (embed_writer, search_reader, etc.)
- pgvector extension enabled
- Backup retention: 14 days

**Redis Memorystore:**
- Standard HA tier
- VPC-only access
- No public endpoint

---

## Recommendations

### Priority 1 (Should Do)

1. **Rotate API Gateway Key**
   - The key `AIzaSyD4fwoF0SMDVsA4A1Ip0_dT-qfP1OYPODs` should be rotated
   - Update documentation to reference Secret Manager retrieval
   ```bash
   # Replace hardcoded keys with:
   API_KEY=$(gcloud secrets versions access latest --secret=gateway-api-key-tenant-alpha)
   ```

### Priority 2 (Nice to Have)

2. **Consider Content-Security-Policy Refinement**
   - Review CSP headers for frontend if not already customized

3. **Add Security Monitoring Alerts**
   - Alert on failed authentication attempts
   - Alert on rate limit exceeded events
   - Alert on unusual API patterns

### Priority 3 (Future Enhancement)

4. **Implement API Key Rotation Schedule**
   - Set up automated key rotation for long-lived keys

5. **Add Security Headers to API Gateway**
   - Additional headers at the gateway level for defense in depth

---

## Compliance Checklist

| Control | Status | Evidence |
|---------|--------|----------|
| Authentication required for all endpoints | ✅ | CloudBuild: `--no-allow-unauthenticated` |
| JWT token validation | ✅ | `auth.ts:252-284` |
| Role-based access control | ✅ | `firestore.rules` |
| Input validation | ✅ | Schema validation in config.ts |
| SQL injection prevention | ✅ | Parameterized queries + allowlist |
| XSS prevention | ✅ | DOMPurify in UI |
| Secrets in Secret Manager | ✅ | CloudBuild `--set-secrets` |
| No hardcoded credentials | ⚠️ | One API key in docs (low risk) |
| Rate limiting | ✅ | `rate_limit.ts`, `server.ts` |
| CORS properly configured | ✅ | `config.ts:202-227` |
| Security headers | ✅ | Helmet.js |
| VPC isolation | ✅ | `--vpc-egress=private-ranges-only` |
| Audit logging | ✅ | Structured logs, Firestore audit_logs |
| Dependency vulnerabilities | ✅ | 0 vulnerabilities |

---

## Conclusion

The Headhunter application has a **robust security architecture** with defense-in-depth controls at multiple layers:

1. **Network Layer:** VPC isolation, private egress, IAM authentication
2. **Application Layer:** JWT validation, rate limiting, input validation
3. **Data Layer:** Firestore rules, parameterized SQL, encryption at rest

The single finding (API key in documentation) is low risk due to existing mitigating controls. Overall, the application is production-ready from a security perspective.

---

*Report generated by Claude Code Security Analysis*
*Next recommended audit: Q2 2026*
