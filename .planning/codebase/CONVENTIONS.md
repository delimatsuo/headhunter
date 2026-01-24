# Coding Conventions

**Analysis Date:** 2026-01-24

## Naming Patterns

**Files:**
- Lowercase with hyphens: `search-service.ts`, `pgvector-client.ts`, `embed-client.ts`
- Test files use double extension: `*.test.ts` or `*.spec.ts`
- Configuration modules: `config.ts` (exported function: `getSearchServiceConfig()`)
- Types file: `types.ts` (collects all interfaces)
- Routes file: `routes.ts` with export async function `registerRoutes()`
- Service classes: PascalCase ending in Service: `SearchService`, `EnrichmentService`
- Client classes: PascalCase ending in Client: `PgVectorClient`, `EmbedClient`, `RerankClient`, `SearchRedisClient`

**Functions:**
- camelCase: `computeSkillMatches()`, `hybridSearch()`, `extractCountryFromJobDescription()`
- Prefix private functions with underscore: `_createRerankClient()` (marked with void to silence unused warnings)
- Factory functions: `errorFactory()`, returns specialized error constructor
- Async functions declared explicitly: `async function registerRoutes()`
- Prefix unused parameters with underscore: `_request`, `_firestoreTypeCheck`

**Variables:**
- camelCase for constants and variables: `baseConfigTemplate`, `cachedConfig`, `generatedEmbedding`
- CONSTANT_CASE for compile-time constants: `ALLOWED_SCHEMAS`, `BRAZIL_INDICATORS`, `US_INDICATORS`, `REQUEST_START`, `COST_EVENTS`
- Symbol constants for metadata keys: `REQUEST_START = Symbol('requestStart')`, `COST_EVENTS = Symbol('costEvents')`

**Types:**
- PascalCase interfaces: `SearchServiceConfig`, `PgVectorConfig`, `HybridSearchRequest`
- Suffix types with their category: Config interfaces, Response objects, Request objects
- Type aliases for complex signatures: `ErrorFactory = (message: string, details?: Record<string, unknown>) => ServiceError`
- Service-specific type files located in service directory: `services/hh-search-svc/src/types.ts`

**Classes:**
- PascalCase: `SearchService`, `CircuitBreaker`, `ServiceError`
- Extend Error class with `name` property: `this.name = 'ServiceError'`
- Keep private fields explicitly: `private state: CircuitBreakerState = 'CLOSED'`

## Code Style

**Formatting:**
- Tool: ESLint with Prettier integration (`eslint-config-prettier`)
- 2-space indentation (inferred from codebase)
- Single quotes for strings (TypeScript convention)
- Trailing commas in multiline arrays/objects
- Line wrap at readability point

**Linting:**
- Config: `services/.eslintrc.js`
- Parser: `@typescript-eslint/parser`
- Extends: `eslint:recommended`, `plugin:@typescript-eslint/recommended`, `plugin:import/recommended`, `plugin:jest/recommended`, `prettier`
- No default exports: `import/no-default-export: 'error'`
- Unused parameters with `^_` prefix allowed: `@typescript-eslint/no-unused-vars: ['error', { argsIgnorePattern: '^_' }]`
- Explicit any is warning: `@typescript-eslint/no-explicit-any: 'warn'`
- Import ordering enforced with newlines between groups
- Jest focused tests forbidden: `jest/no-focused-tests: 'error'`

## Import Organization

**Order:**
1. Built-in modules and external packages: Node stdlib, npm packages
2. Internal packages: `@hh/common`, service-specific imports
3. Local files: relative imports (`./config`, `../types`)
- Newlines required between groups

**Path Aliases:**
- `@hh/common` resolves to `services/common/src/*` (configured in Jest moduleNameMapper)
- Workspace references via TypeScript `references` field in tsconfig.json
- Import resolver: `eslint-import-resolver-typescript`

**Import Style:**
- Named imports preferred: `import { badRequestError, getFirestore } from '@hh/common'`
- Type imports: `import type { SearchServiceConfig } from './config'`
- Wildcard for services: `import fp from 'fastify-plugin'` (no named export)

## Error Handling

**Patterns:**
- Custom `ServiceError` class with statusCode, code, and details properties
- Error factory pattern: `errorFactory(statusCode, code)` returns constructor
- Pre-built error constructors: `badRequestError()`, `unauthorizedError()`, `notFoundError()`, `internalError()`, `tooManyRequestsError()`
- Cause chaining: `{ cause: Error }` option in ServiceError constructor
- Sanitize errors before responding: `sanitizeError(err)` returns statusCode + ErrorResponse payload
- Async error persistence to Firestore for 5xx errors: `persistError(request, error, statusCode)`
- Wrap external calls: `CircuitBreaker.exec()` for transient failures
- Retry with exponential backoff: `withRetry(fn, { retries, factor, minTimeoutMs })`

**Example:**
```typescript
// Throw errors with context
throw badRequestError('Invalid search query', { field: 'query', received: value });

// Circuit breaker pattern
const breaker = new CircuitBreaker({ failureThreshold: 3, successThreshold: 1, timeoutMs: 30_000 });
try {
  return await breaker.exec(() => embedClient.generateEmbedding(query));
} catch (err) {
  // Handle OPEN state or propagate
}

// Retry with exponential backoff
const result = await withRetry(() => pgClient.hybridSearch(params), {
  retries: 2,
  factor: 2,
  minTimeoutMs: 200
});
```

## Logging

**Framework:** Pino (structured JSON logging)

**Patterns:**
- Root logger created once: `buildRootLogger()` returns singleton
- Get logger with bindings: `getLogger({ module: 'search-service' })`
- Child loggers preserve bindings: `logger.child(bindings)`
- Info/warn/error/debug levels available
- Request logging plugin adds requestId, tenantId, traceId automatically
- Cost metrics via `emitCostMetric(entry)` to separate cost_logs stream
- Plugin hook attachments: `fastify.addHook('onRequest', ...)`, `fastify.addHook('onResponse', ...)`

**Usage:**
```typescript
import { getLogger } from '@hh/common';

const logger = getLogger({ module: 'my-module' });
logger.info({ candidateId, score }, 'Candidate ranked');
logger.warn({ err }, 'Request failed with client error.');
logger.error({ err, requestId }, 'Request failed with server error.');
```

## Comments

**When to Comment:**
- Explain "why" not "what": code explains itself, comments explain intent
- Document security decisions: SQL injection prevention patterns
- Document country/location detection heuristics: BRAZIL_INDICATORS list
- Document public API expectations in JSDoc on exported functions
- Mark unused functions with `void _func;` to silence warnings

**JSDoc/TSDoc:**
- Used minimally on functions exported from services
- Type signatures provide most documentation
- Complex configuration loading gets comments explaining defaults and overrides

**Example:**
```typescript
// Security: Allowed schema and table names to prevent SQL injection via env misconfiguration
const ALLOWED_SCHEMAS = ['search', 'public', 'test', 'sourcing'] as const;

// Country indicators for auto-extraction from job descriptions
const BRAZIL_INDICATORS = [
  'são paulo', 'sao paulo', 'rio de janeiro',
  // ... more indicators
];
```

## Function Design

**Size:** Small, focused functions (20-50 lines typical)
- Helper functions extracted: `computeSkillMatches()`, `extractCountryFromJobDescription()`, `parseTraceContext()`
- Complex logic decomposed into named steps
- Async functions keep business logic away from infrastructure

**Parameters:**
- Destructured options objects: `{ statusCode = 500, code = 'internal', details, cause } = {}`
- Config objects bundled: pass `SearchServiceConfig` rather than 10 individual params
- Interface for dependencies: `interface HybridSearchDependencies` groups service dependencies
- Options with sensible defaults in destructuring

**Return Values:**
- Explicit return types: `: Promise<T>`, `: SearchServiceConfig`, `: ServiceError`
- Nullable returns typed: `: string | null`, `: undefined`
- Complex returns as typed objects: `{ matches: string[], coverage: number }`
- Factories return typed constructors: `ErrorFactory = (...) => ServiceError`

## Module Design

**Exports:**
- Named exports: `export function registerRoutes()`, `export class SearchService`
- No default exports per lint rule
- Export interfaces alongside implementations
- Config getters return full config object: `getSearchServiceConfig(): SearchServiceConfig`

**Barrel Files:**
- Common exports in `services/common/src/index.ts`
- Re-export from submodules: `export { getConfig } from './config'`
- Collected types in service `types.ts` files
- Services import from `@hh/common` for shared utilities

**Example:**
```typescript
// services/common/src/index.ts
export { getConfig, type ServiceConfig } from './config';
export { badRequestError, ServiceError, CircuitBreaker, withRetry } from './errors';
export { getLogger } from './logger';
export { getFirestore } from './firestore';
```

---

*Convention analysis: 2026-01-24*
