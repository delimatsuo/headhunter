# HeadHunter Security Audit Report v2

**Date:** January 8, 2026
**Auditor:** Claude Code (Senior Security Analyst)
**Status:** Follow-up Security Audit
**Project:** headhunter-ai-0088

---

## Executive Summary

This comprehensive security audit follows the previous deep infrastructure audit. The application has been reviewed across authentication, authorization, injection vulnerabilities, secrets management, API security, infrastructure configuration, and logging practices.

### Overall Risk Assessment

| Category | Status | Risk Level |
|----------|--------|------------|
| Authentication & Authorization | Excellent | LOW |
| SQL Injection Prevention | Excellent | LOW |
| XSS Prevention | Good | LOW |
| NPM Dependencies (services) | Excellent | LOW |
| NPM Dependencies (functions) | Excellent | LOW |
| NPM Dependencies (UI) | Needs attention | HIGH |
| CloudBuild Security | Partially hardened | HIGH |
| Secrets Management | Good with notes | MEDIUM |
| Input Validation | Good | LOW |
| Firestore Security Rules | Excellent | LOW |
| Storage Security Rules | Excellent | LOW |
| Rate Limiting | Implemented | LOW |
| Security Headers | Implemented | LOW |

---

## Critical Findings

### 1. HIGH: CloudBuild Files Missing Security Flags

**Severity:** HIGH
**Affected Files:** 7 of 8 CloudBuild configurations

Only `hh-search-svc-cloudbuild.yaml` has been properly hardened. The following files are missing critical security flags:

| File | Missing Flags |
|------|---------------|
| `hh-embed-svc-cloudbuild.yaml` | All security flags |
| `hh-rerank-svc-cloudbuild.yaml` | All security flags |
| `hh-enrich-svc-cloudbuild.yaml` | All security flags |
| `hh-evidence-svc-cloudbuild.yaml` | All security flags |
| `hh-eco-svc-cloudbuild.yaml` | All security flags |
| `hh-msgs-svc-cloudbuild.yaml` | All security flags |
| `hh-admin-svc-cloudbuild.yaml` | All security flags |

**Required Flags:**
```yaml
- '--no-allow-unauthenticated'
- '--service-account=<service>-production@headhunter-ai-0088.iam.gserviceaccount.com'
- '--vpc-connector=projects/headhunter-ai-0088/locations/us-central1/connectors/svpc-us-central1'
- '--vpc-egress=private-ranges-only'
- '--memory=2Gi'
- '--cpu=2'
- '--min-instances=0'
- '--max-instances=10'
- '--set-secrets=<service-specific-secrets>'
```

**Risk:** Services could be deployed without authentication, exposed publicly without VPC isolation, or missing resource limits.

---

### 2. HIGH: UI NPM Dependency Vulnerabilities

**Severity:** HIGH
**Location:** `headhunter-ui/`

```
Vulnerabilities found:
- @svgr/plugin-svgo (high severity)
- @svgr/webpack (high severity)
- css-select (high severity via nth-check)
```

These vulnerabilities are in the react-scripts dependency chain. A major version upgrade of react-scripts is required.

**Recommendation:**
```bash
cd headhunter-ui
# Option 1: Upgrade react-scripts (breaking changes expected)
npm install react-scripts@latest

# Option 2: Consider migrating to Vite for better security updates
npm create vite@latest
```

---

### 3. MEDIUM: Schema/Table Validation Missing in hh-embed-svc

**Severity:** MEDIUM
**Location:** `services/hh-embed-svc/src/config.ts:133-134`

```typescript
// Current (unvalidated):
schema: process.env.PGVECTOR_SCHEMA ?? 'search',
table: process.env.PGVECTOR_TABLE ?? 'candidate_embeddings',
```

Unlike `hh-search-svc` which validates schema/table names, `hh-embed-svc` uses environment variables directly. This could allow SQL injection via malicious environment configuration.

**Recommendation:** Add the same validation pattern from `hh-search-svc`:
```typescript
const ALLOWED_SCHEMAS = ['search', 'public', 'test'] as const;
const ALLOWED_TABLE_NAME_PATTERN = /^[a-z_][a-z0-9_]{0,62}$/;

schema: validateSchemaName(process.env.PGVECTOR_SCHEMA ?? 'search'),
table: validateTableName(process.env.PGVECTOR_TABLE ?? 'candidate_embeddings'),
```

---

## Positive Security Findings

### Authentication & Authorization
- Firebase Auth with proper JWT verification
- Issuer and audience validation
- Token caching with expiration
- org_id claim extraction for multi-tenancy
- Gateway token support with JWKS validation

### SQL Injection Prevention
- **All SQL queries use parameterized placeholders** ($1, $2, etc.)
- User input never directly concatenated into SQL
- Example from `pgvector-client.ts`:
  ```typescript
  filters.push(`LOWER(cp.location) = ANY($${parameterIndex}::text[])`);
  ```

### XSS Prevention
- **DOMPurify used for all dangerouslySetInnerHTML content**
- Example from `CandidateResults.tsx`:
  ```tsx
  dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(skill) }}
  ```

### NPM Dependencies
| Package Set | Vulnerabilities |
|-------------|-----------------|
| services/ | 0 |
| functions/ | 0 |
| headhunter-ui/ | 3+ (in react-scripts) |

### Security Headers & Middleware
- Helmet.js configured for security headers
- CORS allowlist configured (not wildcard)
- Rate limiting with tenant-aware key generation
- Trust proxy enabled for Cloud Run

### Firestore Security Rules
- Authentication required for all operations
- Organization-based access control (`isOrgMember()`)
- Role-based permissions (recruiter, admin, super_admin)
- Default deny rule at end
- Write operations disabled for client (Cloud Functions only)

### Storage Security Rules
- Authentication required for reads
- File size limits (10MB)
- Owner-only access for user uploads
- Default deny rule

### Secrets Management
- `.mcp.json` in `.gitignore` (API keys not tracked)
- `functions/.env` in `.gitignore`
- Production secrets in Secret Manager
- No hardcoded production credentials in source

### Logging Security
- Structured logging with tenant/request IDs
- No passwords or tokens logged
- Token verification failures logged appropriately
- ID token acquisition errors sanitized

---

## Action Items

### Immediate (This Week)

| Priority | Issue | Action |
|----------|-------|--------|
| HIGH | CloudBuild security | Add security flags to all 7 remaining CloudBuild files |
| HIGH | UI vulnerabilities | Upgrade react-scripts or migrate to Vite |
| MEDIUM | hh-embed-svc validation | Add schema/table name validation |

### Short-term (Next 2 Weeks)

| Priority | Issue | Action |
|----------|-------|--------|
| MEDIUM | Production security checks | Add startup validation to all services (like hh-search-svc) |
| LOW | API key rotation | Rotate Anthropic API key in .mcp.json if ever committed |

---

## Security Checklist

### Deployment Security
- [x] CORS configured with allowlist
- [x] Rate limiting implemented
- [x] Helmet.js security headers
- [x] Authentication middleware
- [x] Tenant isolation
- [ ] All CloudBuild files hardened (1/8 complete)

### Data Security
- [x] SQL injection prevented (parameterized queries)
- [x] XSS prevented (DOMPurify)
- [x] Firestore rules enforce access control
- [x] Storage rules enforce access control
- [x] Secrets in Secret Manager

### Code Security
- [x] npm audit clean (services, functions)
- [ ] npm audit clean (UI) - needs upgrade
- [x] No hardcoded secrets in source
- [x] Structured security logging

---

## Files Reviewed

### Security-Critical Files
- `services/common/src/auth.ts` - Authentication implementation
- `services/common/src/server.ts` - Server security configuration
- `services/common/src/config.ts` - Configuration with CORS/auth settings
- `services/hh-search-svc/src/config.ts` - Schema validation example
- `services/hh-search-svc/src/pgvector-client.ts` - SQL query patterns
- `services/hh-embed-svc/src/config.ts` - Missing validation
- `services/hh-enrich-svc/src/worker.ts` - Subprocess handling
- `firestore.rules` - Database access control
- `storage.rules` - Storage access control
- `headhunter-ui/src/components/CandidateResults.tsx` - XSS handling

### CloudBuild Files
- `services/hh-search-svc-cloudbuild.yaml` (hardened)
- `services/hh-embed-svc-cloudbuild.yaml` (needs hardening)
- `services/hh-rerank-svc-cloudbuild.yaml` (needs hardening)
- `services/hh-enrich-svc-cloudbuild.yaml` (needs hardening)
- `services/hh-evidence-svc-cloudbuild.yaml` (needs hardening)
- `services/hh-eco-svc-cloudbuild.yaml` (needs hardening)
- `services/hh-msgs-svc-cloudbuild.yaml` (needs hardening)
- `services/hh-admin-svc-cloudbuild.yaml` (needs hardening)

---

*Report generated by Claude Code Security Audit v2*
