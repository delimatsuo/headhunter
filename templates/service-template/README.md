# Service Template

This directory contains a template for creating new Headhunter microservices.

## ⚠️ Important

This is a **template only** and should not be deployed to production. Use it as a starting point for creating new services.

## Usage

1. Copy this directory to `services/hh-{your-service}-svc`
2. Update `package.json`:
   - Change `name` to `@hh/{your-service}-svc`
   - Update `description`
3. Update `src/index.ts`:
   - Change `SERVICE_NAME` default value
   - Add your service-specific initialization
4. Update `src/routes.ts`:
   - Add your API endpoints
5. Update `src/config.ts` (create if needed):
   - Add service-specific configuration
6. Create tests in `src/__tests__/`
7. Add to workspace in `services/package.json` if needed
8. Update `docker-compose.local.yml` with your service
9. Add deployment configuration

## Template Structure

```
hh-example-svc/
├── src/
│   ├── index.ts         # Service bootstrap (use this pattern)
│   ├── routes.ts        # API route registration
│   └── config.ts        # Service configuration (optional)
├── package.json         # Dependencies
├── tsconfig.json        # TypeScript configuration
└── Dockerfile          # Container image definition
```

## Key Patterns

### Bootstrap Pattern

All services follow this initialization pattern:

1. **Load config** - Get service configuration
2. **Build server** - Create Fastify instance with common middleware
3. **Register health endpoints** - BEFORE `server.listen()` (critical for Cloud Run)
4. **Start listening** - Begin accepting connections
5. **Initialize dependencies** - Load in `setImmediate()` for lazy init
6. **Register routes** - Add API endpoints after dependencies ready
7. **Add shutdown handlers** - Clean up on SIGTERM/SIGINT

### Health Endpoints

- `/health` - Basic liveness check (returns immediately)
- `/ready` - Readiness check (registered by `@hh/common`)

### Logging

Use structured logging via Pino (from `@hh/common`):

```typescript
const logger = getLogger({ module: 'my-module' });

logger.info({ key: 'value' }, 'Message');
logger.warn({ error }, 'Warning message');
logger.error({ error }, 'Error message');
```

**Never use `console.log` in production code.**

### Configuration

Load all config from environment variables:

```typescript
const config = {
  myValue: process.env.MY_VALUE ?? 'default',
  myNumber: Number(process.env.MY_NUMBER ?? '42')
};
```

### Error Handling

The `@hh/common` package provides centralized error handling. Just throw errors and they'll be caught:

```typescript
if (!isValid) {
  throw new Error('Validation failed');
}
```

## Deployment

This template is **not deployed to production**. To deploy a new service:

1. Build the service: `npm run build --prefix services/hh-your-svc`
2. Test locally: `docker compose -f docker-compose.local.yml up hh-your-svc`
3. Add to Cloud Run deployment scripts
4. Update API Gateway OpenAPI spec
5. Deploy: `./scripts/deploy-cloud-run-services.sh --services hh-your-svc`

## Related Documentation

- `ARCHITECTURE.md` - Overall system architecture
- `CLAUDE.md` - Development guidelines
- `docs/HANDOVER.md` - Operations runbook
- `services/common/README.md` - Shared middleware documentation
