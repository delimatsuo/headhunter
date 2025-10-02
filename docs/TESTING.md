# Testing Strategy

**Last Updated**: 2025-10-02
**Owner**: Engineering Team

---

## Overview

This document defines the testing strategy for Headhunter microservices. We follow a **test-driven development (TDD)** approach with comprehensive coverage requirements before production deployment.

## Testing Pyramid

```
       /\
      /E2\      End-to-End (10%)
     /----\
    / Integ\    Integration (30%)
   /--------\
  /   Unit   \  Unit Tests (60%)
 /____________\
```

### Coverage Targets

| Type | Target | Current | Status |
|------|--------|---------|--------|
| Unit Tests | 70% | ~4% | 🔴 Critical Gap |
| Integration Tests | 80% | ~20% | 🟡 Needs Work |
| E2E Tests | Key flows | None | 🔴 Missing |
| **Overall** | **75%** | **~10%** | 🔴 **Urgent** |

---

## Test Types

### 1. Unit Tests (60% of tests)

**Purpose**: Test individual functions/classes in isolation

**Scope**:
- Business logic
- Data transformations
- Utility functions
- Configuration parsing
- Client wrappers (mocked dependencies)

**Tools**:
- **Vitest** (preferred for new tests - faster, better DX)
- **Jest** (existing tests)
- **Sinon** for mocking
- **@testcontainers** for ephemeral infrastructure

**Location**: `services/hh-{service}-svc/src/__tests__/`

**Example**:
```typescript
// services/hh-search-svc/src/__tests__/search-service.test.ts
import { describe, it, expect, vi } from 'vitest';
import { SearchService } from '../search-service';

describe('SearchService', () => {
  it('should perform hybrid search with valid query', async () => {
    const mockPgClient = { query: vi.fn().mockResolvedValue([]) };
    const service = new SearchService({ pgClient: mockPgClient });

    const results = await service.hybridSearch({
      query: 'Senior Python Developer',
      tenantId: 'test-tenant',
      limit: 10
    });

    expect(results).toBeDefined();
    expect(mockPgClient.query).toHaveBeenCalled();
  });
});
```

**Run**:
```bash
# Single service
npm test --prefix services/hh-search-svc

# All services
npm test --prefix services

# With coverage
npm run test:coverage --prefix services
```

### 2. Integration Tests (30% of tests)

**Purpose**: Test interactions between services and infrastructure

**Scope**:
- Service-to-service communication
- Database operations (real Postgres)
- Redis caching (real Redis)
- Firestore operations (emulator)
- API endpoint contracts

**Tools**:
- **Vitest** for test framework
- **Testcontainers** for Docker-based infrastructure
- **Supertest** for HTTP testing
- **Docker Compose** for local stack

**Location**: `tests/integration/`

**Example**:
```typescript
// tests/integration/search-flow.test.ts
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import request from 'supertest';

describe('Search Flow Integration', () => {
  let searchUrl: string;
  let embedUrl: string;

  beforeAll(async () => {
    // Start services via docker-compose or testcontainers
    searchUrl = 'http://localhost:7102';
    embedUrl = 'http://localhost:7101';
  });

  it('should generate embedding and perform search', async () => {
    // 1. Generate embedding
    const embedRes = await request(embedUrl)
      .post('/v1/embeddings/generate')
      .set('X-Tenant-ID', 'test-tenant')
      .send({ input: 'Python developer' })
      .expect(200);

    expect(embedRes.body.embedding).toBeDefined();

    // 2. Use embedding in search
    const searchRes = await request(searchUrl)
      .post('/v1/search/hybrid')
      .set('X-Tenant-ID', 'test-tenant')
      .send({
        query: 'Python developer',
        limit: 10
      })
      .expect(200);

    expect(searchRes.body.results).toBeInstanceOf(Array);
  });
});
```

**Run**:
```bash
# With stack running
docker compose -f docker-compose.local.yml up -d
npm run test:integration

# Or use test script
./scripts/test-integration.sh
```

### 3. End-to-End Tests (10% of tests)

**Purpose**: Test complete user flows from UI to database

**Scope**:
- Critical user journeys
- Authentication flows
- Data consistency
- Error handling

**Tools**:
- **Playwright** (planned)
- **Cypress** (alternative)

**Location**: `tests/e2e/` (to be created)

**Planned Flows**:
1. User uploads candidate file → enrichment → search
2. Admin creates tenant → configures settings → invites users
3. Recruiter performs search → views results → bookmarks candidate

---

## Testing Standards

### Required for All Services

1. **Test files must exist** for:
   - `src/index.ts` (bootstrap logic)
   - `src/routes.ts` (API endpoints)
   - `src/config.ts` (configuration parsing)
   - All business logic files

2. **Coverage thresholds** (enforced in CI):
   ```json
   {
     "coverage": {
       "lines": 70,
       "functions": 70,
       "branches": 60,
       "statements": 70
     }
   }
   ```

3. **Test naming convention**:
   ```typescript
   describe('ModuleName', () => {
     describe('functionName', () => {
       it('should do X when Y', () => {
         // test
       });

       it('should throw error when invalid input', () => {
         // error case
       });
     });
   });
   ```

4. **Setup/teardown**:
   ```typescript
   beforeAll(async () => {
     // One-time setup (start containers, load fixtures)
   });

   beforeEach(() => {
     // Per-test setup (reset state)
   });

   afterEach(() => {
     // Per-test cleanup (clear mocks)
   });

   afterAll(async () => {
     // Final cleanup (stop containers)
   });
   ```

---

## Test Data Management

### Fixtures

Store test data in `tests/fixtures/`:

```
tests/fixtures/
├── candidates/
│   ├── valid-candidate.json
│   ├── incomplete-candidate.json
│   └── invalid-candidate.json
├── search-queries/
│   └── sample-queries.json
└── auth/
    └── test-tokens.json
```

### Factories

Use factories for complex objects:

```typescript
// tests/factories/candidate-factory.ts
export function createCandidate(overrides = {}) {
  return {
    id: 'test-123',
    name: 'John Doe',
    email: 'john@example.com',
    skills: ['Python', 'AWS'],
    ...overrides
  };
}
```

### Mocking

**External Services**:
```typescript
// Mock Together AI
vi.mock('@/clients/together-client', () => ({
  TogetherClient: vi.fn().mockImplementation(() => ({
    complete: vi.fn().mockResolvedValue({ text: 'mocked response' })
  }))
}));
```

**Databases** (prefer real):
```typescript
// Use testcontainers for real Postgres
import { PostgreSqlContainer } from '@testcontainers/postgresql';

let container: StartedPostgreSqlContainer;

beforeAll(async () => {
  container = await new PostgreSqlContainer().start();
});
```

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Test

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 20
      - run: npm install --workspaces --prefix services
      - run: npm test --prefix services
      - run: npm run test:coverage --prefix services
      - uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: ankane/pgvector:v0.5.1
        env:
          POSTGRES_PASSWORD: test
      redis:
        image: redis:7-alpine
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm install --workspaces --prefix services
      - run: npm run test:integration
```

### Pre-commit Hooks

```bash
# .husky/pre-commit
npm run lint --prefix services
npm run typecheck --prefix services
npm test --prefix services --run
```

### Merge Requirements

- ✅ All tests pass
- ✅ Coverage >= 70%
- ✅ No TypeScript errors
- ✅ Lint checks pass
- ✅ Code review approved

---

## Performance Testing

### Load Testing

**Tool**: k6

**Scenarios**:
1. **Baseline**: 10 VUs, 30s duration
2. **Stress**: 100 VUs, 5m duration
3. **Spike**: 0→500→0 VUs over 10m

**Example**:
```javascript
// tests/load/search-load.js
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(95)<1200'], // 95% under 1.2s
    http_req_failed: ['rate<0.01'],    // <1% errors
  },
};

export default function() {
  let res = http.post('http://localhost:7102/v1/search/hybrid',
    JSON.stringify({
      query: 'Python developer',
      limit: 10
    }),
    {
      headers: {
        'Content-Type': 'application/json',
        'X-Tenant-ID': 'test-tenant'
      }
    }
  );

  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time OK': (r) => r.timings.duration < 1200,
  });
}
```

**Run**:
```bash
k6 run tests/load/search-load.js
```

---

## Test Environment Setup

### Local Development

1. **Start infrastructure**:
   ```bash
   docker compose -f docker-compose.local.yml up postgres redis firestore pubsub
   ```

2. **Seed test data**:
   ```bash
   npm run seed:test --prefix services
   ```

3. **Run tests**:
   ```bash
   npm test --prefix services
   ```

### CI Environment

Uses ephemeral containers via Testcontainers:

```typescript
import { PostgreSqlContainer } from '@testcontainers/postgresql';
import { GenericContainer } from 'testcontainers';

beforeAll(async () => {
  const postgres = await new PostgreSqlContainer().start();
  const redis = await new GenericContainer('redis:7-alpine')
    .withExposedPorts(6379)
    .start();

  process.env.POSTGRES_URL = postgres.getConnectionUri();
  process.env.REDIS_URL = `redis://${redis.getHost()}:${redis.getMappedPort(6379)}`;
});
```

---

## Troubleshooting

### Tests Failing Locally

1. **Check infrastructure**:
   ```bash
   docker compose ps
   # All services should be "healthy"
   ```

2. **Clear test database**:
   ```bash
   docker compose down -v
   docker compose up -d
   ```

3. **Check environment variables**:
   ```bash
   cat services/hh-search-svc/.env.local
   ```

### Flaky Tests

Common causes:
- **Race conditions**: Add proper `await` statements
- **Shared state**: Use `beforeEach` to reset
- **Timing issues**: Increase timeouts for CI
- **External dependencies**: Mock or use containers

### Slow Tests

Optimization strategies:
- Run unit tests in parallel: `vitest --threads`
- Use `--bail` to stop on first failure
- Skip slow integration tests locally: `it.skip(...)`
- Cache node_modules in CI

---

## Resources

### Documentation
- [Vitest Docs](https://vitest.dev/)
- [Jest Docs](https://jestjs.io/)
- [Testcontainers](https://node.testcontainers.org/)
- [Supertest](https://github.com/visionmedia/supertest)

### Examples
- `tests/examples/` - Sample test patterns
- `templates/service-template/__tests__/` - Service test template

### Help
- Ask in `#engineering-help` Slack channel
- Review existing tests in `hh-search-svc`
- Pair with senior engineer for first test

---

**Next Steps**:
1. Add unit tests to all services (target: 70% coverage)
2. Expand integration test suite
3. Set up Playwright for E2E tests
4. Configure coverage reporting (Codecov)
5. Add performance regression tests

**Target Date**: 2025-10-16 (2 weeks)
