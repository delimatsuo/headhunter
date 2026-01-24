# Testing Patterns

**Analysis Date:** 2026-01-24

## Test Framework

**Runner:**
- Jest (primary) v29.7.0
- Vitest (security tests) for integration scenarios
- Config: `services/jest.config.js` and `jest.config.js` (root)

**Assertion Library:**
- Jest built-in matchers: `expect().toBe()`, `expect().toHaveBeenCalled()`, `expect().toEqual()`

**Run Commands:**
```bash
npm test --prefix services              # Run all service tests
npm test --prefix services/hh-search-svc  # Run specific service tests
npm run test:coverage --prefix services   # Generate coverage reports
SKIP_JEST=1 npm run test:integration --prefix services  # Integration tests
```

## Test File Organization

**Location:**
- Co-located with source code in `__tests__/` subdirectory
- Pattern: `src/__tests__/` for service code, `tests/` directory for root-level tests

**Naming:**
- Unit tests: `*.test.ts` suffix
- Spec-style tests: `*.spec.ts` suffix
- Common pattern across codebase: both suffixes used interchangeably

**Structure:**
```
services/hh-search-svc/
├── src/
│   ├── search-service.ts
│   ├── config.ts
│   ├── __tests__/
│   │   ├── search-service.spec.ts
│   │   ├── config.spec.ts
│   │   ├── pgvector-client.spec.ts
│   │   └── routes.spec.ts
│   └── types.ts

tests/
├── integration/
│   └── enrich-service.test.ts
├── unit/
│   └── admin-service.test.ts
└── security/
    └── auth_integration.test.ts
```

## Test Structure

**Suite Organization:**
```typescript
describe('SearchService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.resetModules();
  });

  afterAll(() => {
    // Restore process.env and module state
  });

  it('uses cached embedding when available', async () => {
    // Setup
    const config = createBaseConfig();
    const pgClient = createPgClient();

    // Mock responses
    pgClient.hybridSearch.mockResolvedValue([pgRow]);
    redisClient.get.mockResolvedValue(cachedEmbedding);

    // Execute
    const service = new SearchService({ config, pgClient, redisClient, ... });
    const response = await service.hybridSearch(context, request);

    // Assert
    expect(pgClient.hybridSearch).toHaveBeenCalledTimes(1);
    expect(response.results).toHaveLength(1);
  });
});
```

**Patterns:**
- Setup phase: Create config, clients, dependencies using factory functions
- Mock phase: `.mockResolvedValue()`, `.mockRejectedValue()` for async behavior
- Execute phase: Call service method with test data
- Assert phase: Verify calls and results

## Mocking

**Framework:** Jest mocks
- `jest.fn()` for function mocks
- `jest.mock()` for module-level mocks
- `jest.resetModules()` after each test

**Patterns:**
```typescript
// Mock Firestore client
jest.mock('firebase-admin/app', () => ({
  getApps: jest.fn(() => []),
  initializeApp: jest.fn(() => ({})),
  applicationDefault: jest.fn(() => ({}))
}));

// Mock external service
const verifyIdTokenMock = jest.fn();
jest.mock('firebase-admin/auth', () => ({
  getAuth: jest.fn(() => ({ verifyIdToken: verifyIdTokenMock }))
}));

// Return value mock
pgClient.hybridSearch.mockResolvedValue([pgRow]);
redisClient.get.mockResolvedValue(cachedEmbedding);

// Setup return on child call
(logger.child as jest.Mock).mockReturnValue(logger);
```

**What to Mock:**
- External services: Firebase Auth, Google Cloud, databases
- HTTP clients: Embed service, rerank service
- Database clients: PgVector, Redis
- Expensive operations: AI processing, external API calls

**What NOT to Mock:**
- Business logic being tested
- Error classes and patterns
- Configuration parsing
- Data structure helpers (e.g., `computeSkillMatches`)

## Fixtures and Factories

**Test Data:**
```typescript
// Factory function creates test config
const baseConfigTemplate = (): SearchServiceConfig => ({
  base: { env: 'test', runtime: { ... } },
  pgvector: { host: 'localhost', port: 5432, ... },
  redis: { host: '127.0.0.1', port: 6379, ... },
  // ... all config sections
});

// Deep clone ensures isolation between tests
const createBaseConfig = (): SearchServiceConfig =>
  JSON.parse(JSON.stringify(baseConfigTemplate())) as SearchServiceConfig;

// Typed factory for clients
const createPgClient = (): PgVectorClient => ({
  hybridSearch: jest.fn(),
  close: jest.fn(),
  healthCheck: jest.fn().mockResolvedValue({ status: 'healthy' }),
  initialize: jest.fn()
} as unknown as PgVectorClient);

// Test data as constants
const pgRow: PgHybridSearchRow = {
  candidate_id: 'cand-001',
  vector_score: 0.5,
  text_score: 0.1,
  hybrid_score: 0.5,
  analysis_confidence: 0.9,
  full_name: 'Test Candidate'
};
```

**Location:**
- Inline in test files for simple data
- Factory functions at top of test file for complex setups
- Shared fixtures in integration tests: `TestJobStore`, `InMemoryRedisClient`

## Coverage

**Requirements:** No target enforced in lint
- Pragmatic: test critical paths, not 100% coverage
- Service boundaries: test public methods thoroughly
- Error paths: test error handling and edge cases

**View Coverage:**
```bash
npm run test:coverage --prefix services
```

## Test Types

**Unit Tests:**
- Location: `src/__tests__/*.test.ts`
- Scope: Test single class or function in isolation
- Mocking: Mock all dependencies (Redis, Postgres, external clients)
- Speed: Fast, <10ms per test typical
- Examples: `search-service.spec.ts`, `config.spec.ts`, `auth.test.ts`

**Integration Tests:**
- Location: `tests/integration/*.test.ts`
- Scope: Multiple components working together
- Mocking: Mock external services, real module loading
- Speed: Slower, may take 100ms+ per test
- Examples: `enrich-service.test.ts` (job store + enrichment worker), `msgs-service.test.ts`
- Environment: Can use test doubles like `InMemoryRedisClient`

**E2E Tests:**
- Framework: Not currently used
- Could add Fastify injection: `app.inject({ method, url, headers })`

## Common Patterns

**Async Testing:**
```typescript
// Test async service methods
it('uses cached embedding when available', async () => {
  redisClient.get.mockResolvedValue(cachedEmbedding);

  const response = await service.hybridSearch(context, { query: 'test' });

  expect(response.results).toHaveLength(1);
});

// Test promise rejection
it('rejects revoked tokens', async () => {
  const revokedError = new Error('auth/id-token-revoked');
  verifyIdTokenMock.mockRejectedValue(revokedError);

  const response = await app.inject({ ... });

  expect(response.statusCode).toBe(401);
});
```

**Error Testing:**
```typescript
// Test custom error class
const error = new ServiceError('Test message', {
  statusCode: 400,
  code: 'bad_request',
  details: { field: 'query' }
});

expect(error.statusCode).toBe(400);
expect(error.code).toBe('bad_request');

// Test error factory
const err = badRequestError('Invalid input', { received: 'bad' });
expect(err).toBeInstanceOf(ServiceError);
expect(err.statusCode).toBe(400);
```

**Fastify Integration:**
```typescript
it('accepts valid gateway tokens', async () => {
  const app = Fastify();
  await app.register(authenticationPlugin);
  app.get('/secure', (request) => ({ uid: request.user?.uid }));

  const response = await app.inject({
    method: 'GET',
    url: '/secure',
    headers: { authorization: `Bearer ${token}` }
  });

  expect(response.statusCode).toBe(200);
  const payload = JSON.parse(response.payload);
  expect(payload.uid).toBe('client-1');

  await app.close();
});
```

**Environment Isolation:**
```typescript
// Preserve original env before tests
const originalEnv = {
  GOOGLE_CLOUD_PROJECT: process.env.GOOGLE_CLOUD_PROJECT,
  AUTH_MODE: process.env.AUTH_MODE
};

// Set test env
process.env.GOOGLE_CLOUD_PROJECT = 'test-project';
process.env.AUTH_MODE = 'none';

// Restore after all tests
afterAll(() => {
  if (originalEnv.GOOGLE_CLOUD_PROJECT) {
    process.env.GOOGLE_CLOUD_PROJECT = originalEnv.GOOGLE_CLOUD_PROJECT;
  } else {
    delete process.env.GOOGLE_CLOUD_PROJECT;
  }
});
```

**Reset Module State:**
```typescript
describe('SearchService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.resetModules();  // Clear require cache
  });

  it('reloads config after reset', async () => {
    const { getSearchServiceConfig, resetSearchServiceConfig } = await import('../config');
    resetSearchServiceConfig();

    const config = getSearchServiceConfig();
    expect(config).toBeDefined();
  });
});
```

## Test Organization Guidelines

**When writing tests:**
1. Create test data factories: `createBaseConfig()`, `createPgClient()`
2. Mock external dependencies: Redis, Postgres, HTTP clients
3. Test happy path first: success cases with correct data
4. Test error paths: invalid input, service failures, timeouts
5. Test call expectations: verify mocks were called with correct args
6. Clean up after tests: `jest.clearAllMocks()`, `jest.resetModules()`

**What to test:**
- Public method contracts: parameters, return values, side effects
- Error handling: proper error codes, messages, details
- Integration points: correct service calls with right arguments
- Configuration: parsing, defaults, validation
- Auth/security: token validation, access control

**What not to test:**
- Third-party library internals
- Implementation details of dependencies
- Trivial getters/setters
- Unused code paths

---

*Testing analysis: 2026-01-24*
