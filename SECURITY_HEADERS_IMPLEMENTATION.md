# Security Headers Implementation Guide

**Date**: October 3, 2025
**Status**: Ready to Implement
**Scope**: API Gateway Security Headers

---

## Overview

This document provides implementation guidance for adding security headers to the Headhunter API Gateway to protect against common web vulnerabilities.

---

## Current Security Posture

### Existing Headers (From Services)

Backend services (hh-admin-svc, etc.) already return these security headers:

```
content-security-policy: default-src 'self';base-uri 'self';font-src 'self' https: data:;form-action 'self';frame-ancestors 'self';img-src 'self' data:;object-src 'none';script-src 'self';script-src-attr 'none';style-src 'self' https: 'unsafe-inline';upgrade-insecure-requests
cross-origin-opener-policy: same-origin
cross-origin-resource-policy: same-origin
origin-agent-cluster: ?1
referrer-policy: no-referrer
strict-transport-security: max-age=15552000; includeSubDomains
x-content-type-options: nosniff
x-dns-prefetch-control: off
x-download-options: noopen
x-frame-options: SAMEORIGIN
x-permitted-cross-domain-policies: none
x-xss-protection: 0
```

✅ **These headers are already being set by Fastify services using `@fastify/helmet`**

---

## Implementation Options

### Option 1: Cloud Armor Security Policy (Recommended)

Use Cloud Armor to add/modify security headers at the edge before requests reach the gateway.

**Advantages**:
- Centralized header management
- No OpenAPI spec changes required
- Can add rate limiting and WAF rules
- Applies to all traffic uniformly

**Implementation**:

```bash
# 1. Create security policy
gcloud compute security-policies create headhunter-gateway-security \
  --description="Security policy for API Gateway with security headers" \
  --project=headhunter-ai-0088

# 2. Add security headers rule
gcloud compute security-policies rules create 1000 \
  --security-policy=headhunter-gateway-security \
  --action=allow \
  --description="Add security headers to all responses" \
  --expression="true" \
  --header-action='
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-XSS-Protection": "0",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": "default-src '\''self'\''; script-src '\''self'\''; object-src '\''none'\''"
  ' \
  --project=headhunter-ai-0088

# 3. Apply policy to backend service (requires Load Balancer)
# Note: API Gateway doesn't directly support Cloud Armor
# This would require setting up Load Balancer in front of API Gateway
```

**Note**: API Gateway doesn't directly support Cloud Armor. This option requires an additional GCP Load Balancer layer.

### Option 2: Custom Response Headers in OpenAPI Spec

Add response headers directly in the OpenAPI specification.

**Advantages**:
- No additional infrastructure
- Headers documented in API spec
- Version controlled with API

**Disadvantages**:
- Headers defined per endpoint
- More verbose OpenAPI spec
- Requires gateway redeployment for changes

**Implementation**:

Create `config/security/security-headers.yaml`:

```yaml
# Security headers template for OpenAPI responses
securityHeaders:
  X-Frame-Options:
    description: Prevents clickjacking attacks
    schema:
      type: string
      enum: [DENY]
  X-Content-Type-Options:
    description: Prevents MIME-sniffing attacks
    schema:
      type: string
      enum: [nosniff]
  Strict-Transport-Security:
    description: Enforces HTTPS connections
    schema:
      type: string
      example: "max-age=31536000; includeSubDomains; preload"
  Content-Security-Policy:
    description: Mitigates XSS and injection attacks
    schema:
      type: string
      example: "default-src 'self'; script-src 'self'; object-src 'none'"
  Referrer-Policy:
    description: Controls referrer information
    schema:
      type: string
      enum: [strict-origin-when-cross-origin]
  Permissions-Policy:
    description: Controls browser features
    schema:
      type: string
      example: "geolocation=(), microphone=(), camera=()"
```

Then update OpenAPI endpoints to reference these headers:

```yaml
paths:
  /health:
    get:
      summary: Gateway health check
      responses:
        '200':
          description: Gateway is healthy
          headers:
            $ref: '#/components/headers/SecurityHeaders'
```

### Option 3: Backend Service Headers (Current Approach)

**Status**: ✅ Already Implemented

All Fastify services use `@fastify/helmet` which automatically sets security headers:

```typescript
// services/common/src/server.ts
import helmet from '@fastify/helmet';

server.register(helmet, {
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'"],
      objectSrc: ["'none'"],
      // ...
    }
  },
  hsts: {
    maxAge: 15552000,
    includeSubDomains: true
  }
});
```

**Verification**:

```bash
curl -I https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/health
```

Output shows security headers are already present (see "Current Security Posture" section above).

---

## Recommended Implementation

### Phase 1: Document Current Headers (Completed ✅)

Backend services already return comprehensive security headers via `@fastify/helmet`.

### Phase 2: Add Missing Headers

Add these additional headers to improve security:

```typescript
// services/common/src/server.ts

server.register(helmet, {
  // ... existing config ...

  // Add these new headers:
  permissionsPolicy: {
    features: {
      geolocation: ["'none'"],
      microphone: ["'none'"],
      camera: ["'none'"],
      payment: ["'none'"],
      usb: ["'none'"]
    }
  },

  crossOriginEmbedderPolicy: { policy: "require-corp" },
  crossOriginOpenerPolicy: { policy: "same-origin" },
  crossOriginResourcePolicy: { policy: "same-origin" },

  originAgentCluster: true,

  dnsPrefetchControl: { allow: false },

  ieNoOpen: true,

  noSniff: true,

  referrerPolicy: { policy: "strict-origin-when-cross-origin" }
});
```

### Phase 3: Configure CSP for API Gateway

Update Content-Security-Policy for API endpoints:

```typescript
contentSecurityPolicy: {
  directives: {
    defaultSrc: ["'self'"],
    baseUri: ["'self'"],
    fontSrc: ["'self'", "https:", "data:"],
    formAction: ["'self'"],
    frameAncestors: ["'none'"],  // API should not be framed
    imgSrc: ["'self'", "data:"],
    objectSrc: ["'none'"],
    scriptSrc: ["'self'"],
    scriptSrcAttr: ["'none'"],
    styleSrc: ["'self'", "https:", "'unsafe-inline'"],
    upgradeInsecureRequests: []
  }
}
```

---

## Implementation Steps

### Step 1: Update Common Library

```bash
# Edit services/common/src/server.ts
# Add enhanced helmet configuration as shown above
```

### Step 2: Rebuild and Deploy Services

```bash
# Build all services
cd services && npm run build

# Deploy updated services
for service in hh-admin-svc hh-embed-svc hh-search-svc hh-rerank-svc hh-evidence-svc hh-eco-svc hh-msgs-svc hh-enrich-svc; do
  gcloud run deploy $service-production \
    --source=services/$service \
    --region=us-central1 \
    --project=headhunter-ai-0088
done
```

### Step 3: Verify Headers

```bash
# Test each service endpoint
curl -I https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/health
curl -I https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/embeddings/generate
curl -I https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev/v1/admin/snapshots
```

### Step 4: Security Header Validation

Use online tools to validate header configuration:

- https://securityheaders.com
- https://observatory.mozilla.org
- https://csp-evaluator.withgoogle.com

---

## Security Headers Reference

### Required Headers (All Present ✅)

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `SAMEORIGIN` or `DENY` | Prevent clickjacking |
| `Content-Security-Policy` | (see config) | Prevent XSS, injection |
| `Referrer-Policy` | `no-referrer` or `strict-origin-when-cross-origin` | Control referrer info |

### Recommended Headers (Some Missing ⚠️)

| Header | Value | Purpose | Status |
|--------|-------|---------|--------|
| `Permissions-Policy` | `geolocation=(), camera=()` | Disable dangerous features | ⚠️ Add |
| `Cross-Origin-Embedder-Policy` | `require-corp` | Isolate resources | ⚠️ Add |
| `Cross-Origin-Opener-Policy` | `same-origin` | ✅ Present | ✅ Present |
| `Cross-Origin-Resource-Policy` | `same-origin` | ✅ Present | ✅ Present |

---

## Testing

### Automated Header Tests

Create `tests/security/headers.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';

describe('Security Headers', () => {
  const gatewayUrl = 'https://headhunter-api-gateway-production-d735p8t6.uc.gateway.dev';

  it('should return HSTS header', async () => {
    const response = await fetch(`${gatewayUrl}/health`);
    expect(response.headers.get('strict-transport-security')).toContain('max-age');
  });

  it('should return X-Content-Type-Options', async () => {
    const response = await fetch(`${gatewayUrl}/health`);
    expect(response.headers.get('x-content-type-options')).toBe('nosniff');
  });

  it('should return CSP header', async () => {
    const response = await fetch(`${gatewayUrl}/health`);
    expect(response.headers.get('content-security-policy')).toContain("default-src");
  });

  it('should return Permissions-Policy', async () => {
    const response = await fetch(`${gatewayUrl}/health`);
    expect(response.headers.get('permissions-policy')).toBeTruthy();
  });
});
```

Run tests:

```bash
npm test tests/security/headers.test.ts
```

---

## Compliance

### OWASP Top 10 Coverage

| Vulnerability | Mitigated By | Status |
|---------------|--------------|--------|
| Injection | CSP, input validation | ✅ |
| Broken Authentication | JWT validation, HTTPS | ✅ |
| Sensitive Data Exposure | HSTS, encryption at rest | ✅ |
| XML External Entities | Not applicable (JSON API) | N/A |
| Broken Access Control | IAM policies, JWT | ✅ |
| Security Misconfiguration | Helmet defaults | ✅ |
| XSS | CSP, X-XSS-Protection | ✅ |
| Insecure Deserialization | Input validation | ✅ |
| Using Components with Known Vulnerabilities | Dependabot | ⏳ |
| Insufficient Logging & Monitoring | Cloud Logging | ⏳ |

---

## Troubleshooting

### Headers Not Appearing

1. **Check service deployment**:
   ```bash
   gcloud run services describe SERVICE_NAME \
     --region=us-central1 \
     --project=headhunter-ai-0088 | grep "Latest Revision"
   ```

2. **Verify helmet is registered**:
   ```bash
   grep -r "helmet" services/common/src/
   ```

3. **Test service directly** (bypass gateway):
   ```bash
   curl -I https://hh-admin-svc-production-akcoqbr7sa-uc.a.run.app/health \
     -H "Authorization: Bearer $(gcloud auth print-identity-token)"
   ```

### CSP Blocking Legitimate Resources

1. **Check browser console** for CSP violations
2. **Update CSP directives** in `services/common/src/server.ts`
3. **Use CSP report-uri** to collect violations:
   ```typescript
   contentSecurityPolicy: {
     directives: {
       // ... existing directives
       reportUri: '/csp-violation-report'
     }
   }
   ```

---

## Production Readiness Checklist

- [✅] **HSTS Header**: Force HTTPS connections
- [✅] **X-Content-Type-Options**: Prevent MIME sniffing
- [✅] **X-Frame-Options**: Prevent clickjacking
- [✅] **CSP**: Mitigate XSS attacks
- [✅] **Referrer-Policy**: Control referrer information
- [✅] **X-XSS-Protection**: Legacy XSS protection
- [✅] **Cross-Origin Headers**: Resource isolation
- [⚠️] **Permissions-Policy**: Disable dangerous browser features (add)
- [ ] **Security headers validated**: Run securityheaders.com scan
- [ ] **CSP tested**: No legitimate resources blocked
- [ ] **Automated tests**: Header validation tests passing

---

## Next Steps

1. **Add Permissions-Policy header** to helmet configuration
2. **Run security headers scan** on production gateway
3. **Create automated tests** for security headers
4. **Document CSP violation handling** in runbook
5. **Set up security header monitoring** in Cloud Monitoring

---

## Related Documentation

- `AUDIT_REPORT.md` - Security audit findings
- `SECRETS_AUDIT_REPORT.md` - Secrets management audit
- `CURRENT_STATUS.md` - System status

---

## References

- OWASP Secure Headers Project: https://owasp.org/www-project-secure-headers/
- MDN Security Headers: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers#security
- @fastify/helmet Documentation: https://github.com/fastify/fastify-helmet
- Google Cloud Security Best Practices: https://cloud.google.com/security/best-practices

---

**Created**: October 3, 2025
**Status**: Most headers already implemented, minor enhancements needed
**Owner**: Security Team
