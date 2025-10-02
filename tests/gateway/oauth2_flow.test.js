const { getMissingEnv, requestToken } = require('./utils');

const missing = getMissingEnv();

function decodeToken(token) {
  const [, payload] = token.split('.');
  const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(normalized.length + (4 - (normalized.length % 4)) % 4, '=');
  const json = Buffer.from(padded, 'base64').toString('utf8');
  return JSON.parse(json);
}

describe('API Gateway OAuth2 flow', () => {
  if (missing.length > 0) {
    test.skip(`skipping because ${missing.join(', ')} env vars are not set`, () => {});
    return;
  }

  let token;
  let payload;

  beforeAll(async () => {
    token = await requestToken();
    payload = decodeToken(token);
  }, 20000);

  test('returns bearer access token', () => {
    expect(typeof token).toBe('string');
    expect(token.startsWith('ey')).toBe(true);
  });

  test('contains tenant-scoped claims', () => {
    const expectedTenant = process.env.TENANT_ID;
    const org = payload.org_id || payload.orgId || payload.tenant_id || payload.tenantId;
    expect(org).toBe(expectedTenant);
  });

  test('issuer and audience align with configuration', () => {
    if (process.env.GATEWAY_AUDIENCE) {
      expect(payload.aud).toBe(process.env.GATEWAY_AUDIENCE);
    }

    if (process.env.EXPECTED_ISSUER) {
      expect(payload.iss).toBe(process.env.EXPECTED_ISSUER);
    }
  });

  test('token expiry is within the expected window', () => {
    const nowSeconds = Math.floor(Date.now() / 1000);
    expect(payload.exp).toBeGreaterThan(nowSeconds);
    expect(payload.exp - nowSeconds).toBeLessThanOrEqual(3600);
  });
});
