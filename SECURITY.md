# Security Policy

## Supported Versions

We release security updates for the following versions:

| Version | Supported          | Status |
| ------- | ------------------ | ------ |
| 2.x     | :white_check_mark: | Active development |
| 1.x     | :x:                | End of life |
| < 1.0   | :x:                | No longer supported |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please follow these steps:

### 1. **Do Not** Open a Public Issue

Please do not report security vulnerabilities through public GitHub issues, discussions, or pull requests.

### 2. Report Privately

**Email**: security@ella.jobs (or create a [private security advisory](https://github.com/YOUR_ORG/headhunter/security/advisories/new))

**Include**:
- Type of vulnerability (e.g., SQL injection, XSS, authentication bypass)
- Full paths of affected source files
- Location of the affected source code (tag/branch/commit/URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability
- Your suggested fix (if available)

### 3. Response Timeline

- **Initial Response**: Within 48 hours
- **Triage & Validation**: Within 5 business days
- **Fix Development**: Depends on severity (critical: 7 days, high: 14 days, medium/low: 30 days)
- **Public Disclosure**: After fix is released (coordinated disclosure)

### 4. What to Expect

1. **Acknowledgment**: We'll confirm receipt of your report
2. **Investigation**: We'll investigate and validate the vulnerability
3. **Fix Development**: We'll work on a fix (may request your input)
4. **Testing**: We'll test the fix thoroughly
5. **Release**: We'll release a security patch
6. **Credit**: We'll credit you in the security advisory (unless you prefer to remain anonymous)

## Security Best Practices for Contributors

### Code Review Checklist

- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] All user input is validated and sanitized
- [ ] SQL queries use parameterized statements
- [ ] Authentication and authorization checks are in place
- [ ] Sensitive data is encrypted at rest and in transit
- [ ] Error messages don't leak sensitive information
- [ ] Dependencies are up-to-date and scanned for vulnerabilities

### Secrets Management

**Never commit**:
- `.env` files with real credentials
- `*-key.json` files (GCP service account keys)
- `credentials/` directory contents
- Any file containing passwords, API keys, or tokens

**Use instead**:
- Environment variables
- Secret Manager (GCP)
- `.env.example` files with placeholder values

### Dependency Security

Run security audits regularly:

```bash
# Node.js dependencies
npm audit
npm audit fix

# Python dependencies
pip-audit
safety check
```

## Security Features

### Authentication & Authorization

- **JWT validation**: All API requests require valid JWT tokens
- **Tenant isolation**: Multi-tenant architecture with strict data separation
- **Role-based access control (RBAC)**: Granular permissions per user role

### Data Protection

- **Encryption in transit**: TLS 1.3 for all external connections
- **Encryption at rest**: Cloud SQL encryption, Firestore encryption
- **PII handling**: Minimal PII collection, audit logging for access

### Network Security

- **VPC isolation**: Services run in private VPC
- **Cloud Armor**: DDoS protection and WAF rules (planned)
- **API Gateway**: Rate limiting, IP allowlisting
- **Service mesh**: mTLS between microservices (future)

### Monitoring & Incident Response

- **Audit logs**: All security-relevant events logged
- **Anomaly detection**: Monitoring for unusual patterns
- **Incident response plan**: Documented in `docs/INCIDENT_RESPONSE.md` (planned)

## Security Headers

All HTTP responses include:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'
```

Implemented via `@fastify/helmet` middleware.

## Vulnerability Disclosure Policy

### Scope

**In Scope**:
- Authentication/authorization bypasses
- SQL injection, XSS, CSRF
- Remote code execution
- Data leakage or exposure
- Privilege escalation
- API security issues

**Out of Scope**:
- Social engineering attacks
- Physical attacks
- Denial of service attacks
- Vulnerabilities in third-party services
- Issues requiring unlikely user interaction

### Rules of Engagement

- **Do not** access, modify, or delete data that isn't yours
- **Do not** perform destructive testing (DoS, data deletion)
- **Do not** pivot to other systems or networks
- **Test only** in development/staging environments (not production)
- **Respect** rate limits and resource constraints

### Safe Harbor

We commit to:
- Not pursue legal action against security researchers who follow this policy
- Work with you to understand and resolve the issue quickly
- Recognize your contribution publicly (if you wish)

## Security Updates

### Subscribing to Updates

- Watch this repository for security advisories
- Subscribe to our security mailing list: security-announce@ella.jobs

### Update Schedule

- **Critical vulnerabilities**: Patched within 7 days
- **High severity**: Patched within 14 days
- **Medium/Low severity**: Patched in next regular release

## Compliance

Headhunter is designed to comply with:

- **GDPR**: EU data protection regulation
- **CCPA**: California Consumer Privacy Act
- **SOC 2 Type II**: Security, availability, confidentiality (planned)
- **ISO 27001**: Information security management (planned)

## Security Contacts

- **Security Team**: security@ella.jobs
- **Privacy Questions**: privacy@ella.jobs
- **General Inquiries**: support@ella.jobs

## Hall of Fame

We recognize security researchers who help us keep Headhunter secure:

<!-- Security researchers will be listed here after coordinated disclosure -->

---

**Last Updated**: 2025-10-02
**Next Review**: 2026-01-02 (quarterly)
