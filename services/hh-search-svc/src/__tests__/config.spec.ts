// Jest provides describe, expect, it, afterEach as globals
const ORIGINAL_ENV = { ...process.env };

afterEach(async () => {
  process.env = { ...ORIGINAL_ENV };
  const { resetSearchServiceConfig } = await import('../config');
  resetSearchServiceConfig();
});

describe('config', () => {
  it('trims whitespace in PGVECTOR_PASSWORD', async () => {
    process.env.FIREBASE_PROJECT_ID = 'test-project';
    process.env.PGVECTOR_PASSWORD = 'secret-password\n';
    process.env.ENABLE_GATEWAY_TOKENS = 'false';
    process.env.AUTH_MODE = 'none';

    const { getSearchServiceConfig, resetSearchServiceConfig } = await import('../config');
    resetSearchServiceConfig();

    const config = getSearchServiceConfig();

    expect(config.pgvector.password).toBe('secret-password');
  });
});
