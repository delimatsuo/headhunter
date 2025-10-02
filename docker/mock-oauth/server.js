import Fastify from 'fastify';
import { readFileSync } from 'node:fs';
import { createHash, createPrivateKey, createPublicKey } from 'node:crypto';
import { SignJWT, exportJWK } from 'jose';

const port = Number.parseInt(process.env.MOCK_OAUTH_PORT ?? '8081', 10);
const issuerFromEnv = process.env.MOCK_OAUTH_ISSUER ?? `http://localhost:${port}/`;
const issuer = issuerFromEnv.endsWith('/') ? issuerFromEnv : `${issuerFromEnv}/`;
const audience = process.env.MOCK_OAUTH_AUDIENCE ?? 'headhunter-local';
const defaultTenant = process.env.MOCK_OAUTH_DEFAULT_TENANT ?? 'tenant-alpha';
const tenantList = (process.env.MOCK_OAUTH_TENANTS ?? defaultTenant)
  .split(',')
  .map((value) => value.trim())
  .filter((value) => value.length > 0);
const tenants = tenantList.length > 0 ? tenantList : [defaultTenant];

const privatePem = readFileSync(new URL('./keys/private.pem', import.meta.url));
const publicPem = readFileSync(new URL('./keys/public.pem', import.meta.url));

const privateKey = createPrivateKey({ key: privatePem, format: 'pem' });
const publicKey = createPublicKey({ key: publicPem, format: 'pem' });
const jwk = await exportJWK(publicKey);
const kid = createHash('sha256').update(publicPem).digest('hex').slice(0, 16);

jwk.kid = kid;
jwk.alg = 'RS256';
jwk.use = 'sig';

const fastify = Fastify({ logger: true });

fastify.addContentTypeParser('application/x-www-form-urlencoded', { parseAs: 'string' }, (req, body, done) => {
  try {
    const parsed = Object.fromEntries(new URLSearchParams(body));
    done(null, parsed);
  } catch (error) {
    done(error);
  }
});

fastify.get('/health', async () => ({ status: 'ok', issuer, tenants }));

fastify.get('/.well-known/openid-configuration', async () => ({
  issuer,
  token_endpoint: `${issuer}token`,
  jwks_uri: `${issuer}.well-known/jwks.json`,
  response_types_supported: ['token'],
  grant_types_supported: ['client_credentials', 'password'],
  subject_types_supported: ['public'],
  claims_supported: ['sub', 'tenant_id', 'org_id', 'scope', 'email'],
  token_endpoint_auth_methods_supported: ['client_secret_basic']
}));

fastify.get('/.well-known/jwks.json', async () => ({ keys: [jwk] }));

function resolveTenantId(body) {
  const candidate = body.tenant_id ?? body.tenantId ?? body.org_id ?? defaultTenant;
  if (!tenants.includes(candidate)) {
    throw new Error(`Unknown tenant: ${candidate}`);
  }
  return candidate;
}

fastify.post('/token', async (request, reply) => {
  const body = request.body ?? {};
  let tenantId;
  try {
    tenantId = resolveTenantId(body);
  } catch (error) {
    request.log.warn({ body }, 'Rejected token request for unknown tenant');
    return reply.code(400).send({ error: 'invalid_tenant', error_description: error.message });
  }

  const sub = body.sub ?? `user-${tenantId}`;
  const scope = body.scope ?? 'search:read embeddings:write rerank:invoke evidence:read';
  const email = body.email ?? `${sub}@${tenantId}.example.com`;
  const aud = body.aud ?? audience;
  const expiresIn = Number.parseInt(body.expires_in ?? '3600', 10);

  const claims = {
    scope,
    tenant_id: tenantId,
    org_id: tenantId,
    email,
    roles: body.roles ?? ['recruiter'],
    feature_flags: body.feature_flags ?? ['local-dev']
  };

  const jwt = await new SignJWT(claims)
    .setProtectedHeader({ alg: 'RS256', kid })
    .setIssuer(issuer)
    .setAudience(aud)
    .setExpirationTime(`${expiresIn}s`)
    .setIssuedAt()
    .setNotBefore('0s')
    .setSubject(sub)
    .sign(privateKey);

  return {
    access_token: jwt,
    token_type: 'Bearer',
    expires_in: expiresIn,
    scope,
    tenant_id: tenantId
  };
});

fastify.post('/introspect', async (request, reply) => {
  const body = request.body ?? {};
  const token = body.token ?? body.access_token;
  if (!token) {
    return reply.code(400).send({ active: false, error: 'missing_token' });
  }

  return reply.send({
    active: true,
    iss: issuer,
    aud: audience,
    tenant_id: defaultTenant,
    scope: body.scope ?? 'search:read',
    token,
    exp: Math.floor(Date.now() / 1000) + 3600,
    iat: Math.floor(Date.now() / 1000)
  });
});

fastify.get('/tenants', async () => ({ tenants }));

fastify.setErrorHandler((error, request, reply) => {
  request.log.error({ err: error }, 'Unhandled mock-oauth error');
  reply.status(500).send({ error: 'server_error', message: error.message });
});

const start = async () => {
  try {
    await fastify.listen({ host: '0.0.0.0', port });
    fastify.log.info({ port, issuer }, 'Mock OAuth2 server started');
  } catch (error) {
    fastify.log.error(error, 'Failed to start mock OAuth2 server');
    process.exit(1);
  }
};

start();
