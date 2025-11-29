import type { PgVectorConfig } from '../config';
import { PgVectorClient, PG_FTS_DICTIONARY } from '../pgvector-client';

const connectMock = vi.fn();
const releaseMock = vi.fn();
const queryMock = vi.fn();

const poolInstance = {
  connect: connectMock,
  end: vi.fn(),
  on: vi.fn(),
  totalCount: 0,
  idleCount: 0,
  waitingCount: 0
};

vi.mock('pg', () => {
  return {
    Pool: vi.fn(() => poolInstance)
  };
});

vi.mock('pgvector/pg', () => ({
  registerType: vi.fn(),
  toSql: vi.fn((v) => JSON.stringify(v))
}));

describe('PgVectorClient', () => {
  const logger = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn()
  };

  const baseConfig: PgVectorConfig = {
    host: 'localhost',
    port: 5432,
    database: 'headhunter',
    user: 'search',
    password: 'password',
    ssl: false,
    schema: 'search',
    embeddingsTable: 'candidate_embeddings',
    profilesTable: 'candidate_profiles',
    dimensions: 2,
    poolMax: 4,
    poolMin: 2,
    idleTimeoutMs: 30_000,
    connectionTimeoutMs: 5_000,
    statementTimeoutMs: 30_000,
    enableAutoMigrate: false
  };

  beforeEach(() => {
    connectMock.mockReset();
    releaseMock.mockReset();
    queryMock.mockReset();
    poolInstance.end.mockReset();
    poolInstance.on.mockReset();
    poolInstance.totalCount = 0;
    poolInstance.idleCount = 0;
    poolInstance.waitingCount = 0;

    queryMock.mockImplementation(async (sql, values) => {
      const text = (typeof sql === 'string' ? sql : sql?.text ?? '').toLowerCase();
      const params = Array.isArray(values)
        ? values
        : Array.isArray((sql as { values?: unknown[] })?.values)
          ? ((sql as { values?: unknown[] }).values as unknown[])
          : [];

      if (text.includes('information_schema.schemata')) {
        return { rowCount: 1, rows: [{ schema_name: baseConfig.schema }] };
      }

      if (text.includes('information_schema.columns')) {
        if (params.includes(baseConfig.profilesTable)) {
          return {
            rowCount: 3,
            rows: [
              { column_name: 'legal_basis' },
              { column_name: 'consent_record' },
              { column_name: 'transfer_mechanism' }
            ]
          };
        }
        return { rowCount: 0, rows: [] };
      }

      if (text.includes('pg_get_expr') && text.includes('search_document')) {
        return { rowCount: 1, rows: [{ default_value: "to_tsvector('portuguese'::regconfig, ''::text)" }] };
      }

      if (text.includes(baseConfig.embeddingsTable) || text.includes(baseConfig.profilesTable)) {
        return { rowCount: 1, rows: [] };
      }

      if (text.includes('count(')) {
        return { rowCount: 1, rows: [{ total: '0' }] };
      }

      return { rowCount: 1, rows: [] };
    });

    connectMock.mockResolvedValue({
      query: queryMock,
      release: releaseMock
    });
  });

  it('exposes Portuguese FTS dictionary constant', () => {
    expect(PG_FTS_DICTIONARY).toBe('portuguese');
  });

  it('warms up connections based on poolMin during initialization', async () => {
    const client = new PgVectorClient(baseConfig, logger as any);

    await client.initialize();

    // One connection for infrastructure verification plus warmup connections
    expect(connectMock.mock.calls.length).toBeGreaterThanOrEqual(baseConfig.poolMin + 1);
  });

  it('reports pool statistics in health check', async () => {
    const client = new PgVectorClient(baseConfig, logger as any);
    await client.initialize();

    poolInstance.totalCount = 5;
    poolInstance.idleCount = 2;
    poolInstance.waitingCount = 1;

    const health = await client.healthCheck();

    expect(health.poolSize).toBe(5);
    expect(health.idleConnections).toBe(2);
    expect(health.waitingRequests).toBe(1);
  });
});
