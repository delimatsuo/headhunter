import { readFileSync } from 'fs';
import type { FastifyPluginAsync } from 'fastify';
import fp from 'fastify-plugin';
import type { ServiceAccount } from 'firebase-admin';
import { applicationDefault, cert, getApps, initializeApp, type App, type AppOptions } from 'firebase-admin/app';
import { getAuth, type Auth, type DecodedIdToken } from 'firebase-admin/auth';
import { createRemoteJWKSet, jwtVerify } from 'jose';

import { getConfig, type TokenIssuerConfig } from './config';
import { forbiddenError, unauthorizedError } from './errors';
import { getLogger } from './logger';
import type { AuthenticatedUser } from './types';

let firebaseApp: App | null = null;
let authClient: Auth | null = null;
const jwksCache = new Map<string, { jwks: ReturnType<typeof createRemoteJWKSet>; expiresAt: number; jwksUri: string }>();
const tokenCache = new Map<string, { payload: DecodedIdToken; tokenType: 'firebase' | 'gateway'; expiresAt: number }>();

type Logger = ReturnType<typeof getLogger>;

function getFirebaseApp(): App {
  if (firebaseApp) {
    return firebaseApp;
  }

  const existingApp = getApps()[0];
  if (existingApp) {
    firebaseApp = existingApp;
    return firebaseApp;
  }

  const config = getConfig();
  const logger = getLogger({ module: 'auth' });
  const options: AppOptions = {
    projectId: config.firestore.projectId
  };

  const serviceAccountPath = config.auth.serviceAccountPath;
  if (serviceAccountPath) {
    const serviceAccount = loadServiceAccount(serviceAccountPath, logger);
    if (serviceAccount) {
      options.credential = cert(serviceAccount);
    }
  }

  if (!options.credential) {
    try {
      options.credential = applicationDefault();
    } catch (error) {
      logger.warn({ error }, 'Unable to load default application credentials. Continuing without explicit credential.');
    }
  }

  firebaseApp = initializeApp(options);
  return firebaseApp;
}

function getFirebaseAuth(): Auth {
  if (!authClient) {
    authClient = getAuth(getFirebaseApp());
  }

  return authClient;
}

function loadServiceAccount(path: string, logger: Logger): ServiceAccount | undefined {
  try {
    const contents = readFileSync(path, 'utf8');
    return JSON.parse(contents) as ServiceAccount;
  } catch (error) {
    logger.warn({ error, path }, 'Failed to load service account credentials. Falling back to application defaults.');
    return undefined;
  }
}

function getTokenFromRequest(headers: Record<string, unknown>): string | null {
  const authHeader = headers.authorization ?? headers.Authorization;
  if (typeof authHeader === 'string' && authHeader.startsWith('Bearer ')) {
    return authHeader.slice('Bearer '.length);
  }

  const fallbackHeader = headers['x-firebase-auth'] ?? headers['x-id-token'];
  if (typeof fallbackHeader === 'string') {
    return fallbackHeader;
  }

  return null;
}

function extractOrgId(payload: DecodedIdToken): string | undefined {
  const customClaims = payload as Record<string, unknown>;
  if (typeof customClaims.org_id === 'string') {
    return customClaims.org_id;
  }

  if (typeof customClaims.orgId === 'string') {
    return customClaims.orgId;
  }

  if (typeof customClaims.tenant_id === 'string') {
    return customClaims.tenant_id;
  }

  if (typeof customClaims.tenantId === 'string') {
    return customClaims.tenantId;
  }

  if (typeof customClaims.organization_id === 'string') {
    return customClaims.organization_id;
  }

  if (typeof customClaims.organizationId === 'string') {
    return customClaims.organizationId;
  }

  if (typeof customClaims.org === 'string') {
    return customClaims.org;
  }

  const org = customClaims.org as Record<string, unknown> | undefined;
  if (org && typeof org.id === 'string') {
    return org.id;
  }

  const tenant = customClaims.tenant as Record<string, unknown> | undefined;
  if (tenant) {
    const tenantId = tenant.id ?? tenant.tenant_id;
    if (typeof tenantId === 'string') {
      return tenantId;
    }
  }

  const firebase = customClaims.firebase as Record<string, unknown> | undefined;
  const signInProvider = firebase?.sign_in_provider;
  if (signInProvider === 'custom') {
    const claims = firebase?.identities as Record<string, unknown> | undefined;
    const orgClaim = claims?.org_id;
    if (typeof orgClaim === 'string') {
      return orgClaim;
    }
  }

  return undefined;
}

function getRemoteJwks(issuerConfig: TokenIssuerConfig, cacheTtlSeconds: number) {
  const now = Date.now();
  const cached = jwksCache.get(issuerConfig.issuer);
  if (cached && cached.expiresAt > now && cached.jwksUri === issuerConfig.jwksUri) {
    return cached.jwks;
  }

  const ttlMs = Math.max(cacheTtlSeconds, 30) * 1000;
  const jwks = createRemoteJWKSet(new URL(issuerConfig.jwksUri), {
    cacheMaxAge: ttlMs
  });

  jwksCache.set(issuerConfig.issuer, {
    jwks,
    expiresAt: now + ttlMs,
    jwksUri: issuerConfig.jwksUri
  });

  return jwks;
}

async function verifyGatewayToken(idToken: string): Promise<DecodedIdToken> {
  const config = getConfig();
  if (!config.auth.enableGatewayTokens) {
    throw unauthorizedError('Gateway token support disabled.');
  }

  const logger = getLogger({ module: 'auth' });
  const issuerConfigs = config.auth.issuerConfigs;
  const audiences = config.auth.gatewayAudiences;

  if (issuerConfigs.length === 0) {
    logger.error('Gateway token verification attempted without configured issuers.');
    throw unauthorizedError('Gateway token issuer not configured.');
  }

  if (audiences.length === 0) {
    logger.error('Gateway token verification attempted without configured audiences.');
    throw unauthorizedError('Gateway token audience not configured.');
  }

  const audienceOption = audiences.length === 1 ? audiences[0] : audiences;
  let lastError: unknown;

  for (const issuerConfig of issuerConfigs) {
    try {
      const jwks = getRemoteJwks(issuerConfig, config.auth.tokenCacheTtlSeconds);
      const { payload } = await jwtVerify(idToken, jwks, {
        issuer: issuerConfig.issuer,
        audience: audienceOption,
        clockTolerance: config.auth.tokenClockSkewSeconds
      });

      if (payload.iss && !config.auth.allowedIssuers.includes(payload.iss)) {
        logger.warn({ issuer: payload.iss }, 'Gateway token issuer not allowed.');
        throw unauthorizedError('Token issuer not allowed.');
      }

      return payload as DecodedIdToken;
    } catch (error) {
      lastError = error;
      logger.warn({ error, issuer: issuerConfig.issuer }, 'Gateway token verification failed for issuer.');
    }
  }

  logger.error({ error: lastError }, 'Failed to verify API Gateway token.');
  throw unauthorizedError('Invalid gateway token.');
}

function cacheToken(idToken: string, payload: DecodedIdToken, tokenType: 'firebase' | 'gateway'): void {
  const config = getConfig();
  if (!config.auth.tokenCacheEnabled) {
    return;
  }

  const nowSeconds = Math.floor(Date.now() / 1000);
  const ttlSeconds = Math.max(config.auth.tokenClockSkewSeconds, config.auth.tokenCacheTtlSeconds);
  const expires = payload.exp ?? nowSeconds + ttlSeconds;
  const validUntil = Math.min(expires, nowSeconds + config.auth.tokenCacheTtlSeconds);

  tokenCache.set(idToken, {
    payload,
    tokenType,
    expiresAt: validUntil * 1000
  });
}

function getCachedToken(idToken: string): { payload: DecodedIdToken; tokenType: 'firebase' | 'gateway'; } | null {
  const config = getConfig();
  if (!config.auth.tokenCacheEnabled) {
    return null;
  }

  const entry = tokenCache.get(idToken);
  if (!entry) {
    return null;
  }

  if (Date.now() > entry.expiresAt) {
    tokenCache.delete(idToken);
    return null;
  }

  return { payload: entry.payload, tokenType: entry.tokenType };
}

async function verifyIdToken(idToken: string): Promise<{ payload: DecodedIdToken; tokenType: 'firebase' | 'gateway' }> {
  const config = getConfig();
  const checkRevoked = config.auth.checkRevoked;
  const logger = getLogger({ module: 'auth' });

  const cached = getCachedToken(idToken);
  if (cached) {
    return cached;
  }

  const shouldTryFirebase = config.auth.mode !== 'gateway';
  if (shouldTryFirebase) {
    try {
      const payload = await getFirebaseAuth().verifyIdToken(idToken, checkRevoked);
      if (payload.iss && !config.auth.allowedIssuers.includes(payload.iss)) {
        logger.warn({ issuer: payload.iss }, 'Firebase token issuer not allowed.');
        throw unauthorizedError('Token issuer not allowed.');
      }
      cacheToken(idToken, payload, 'firebase');
      return { payload, tokenType: 'firebase' };
    } catch (firebaseError) {
      logger.warn({ firebaseError }, 'Firebase token verification failed, attempting gateway verification.');
    }
  }

  if (!config.auth.enableGatewayTokens) {
    throw unauthorizedError('Invalid authentication token.');
  }

  const gatewayPayload = await verifyGatewayToken(idToken);
  cacheToken(idToken, gatewayPayload, 'gateway');
  return { payload: gatewayPayload, tokenType: 'gateway' };
}

function buildUser(payload: DecodedIdToken): AuthenticatedUser {
  const orgId = extractOrgId(payload);
  const uid = payload.uid ?? payload.sub ?? (payload as Record<string, unknown>).client_id;

  if (!uid) {
    throw unauthorizedError('Token is missing subject claim.');
  }

  if (!orgId) {
    throw forbiddenError('Token missing org_id claim.');
  }

  return {
    uid,
    email: payload.email ?? undefined,
    displayName: payload.name ?? undefined,
    orgId,
    claims: payload as Record<string, unknown>
  };
}

export const authenticationPlugin: FastifyPluginAsync = fp(async (fastify) => {
  fastify.decorateRequest('user', null);

  fastify.addHook('onRequest', async (request) => {
    if (request.url.startsWith('/health') || request.url.startsWith('/ready')) {
      return;
    }

    const token = getTokenFromRequest(request.headers as Record<string, unknown>);
    if (!token) {
      throw unauthorizedError('Missing bearer token.');
    }

    const { payload, tokenType } = await verifyIdToken(token);
    const user = buildUser(payload);
    request.user = user;
    request.requestContext = request.requestContext ?? { requestId: request.id };
    request.requestContext.user = user;
    const audienceClaim = Array.isArray(payload.aud) ? payload.aud[0] : payload.aud;
    request.requestContext.auth = {
      tokenType,
      issuer: payload.iss,
      audience: typeof audienceClaim === 'string' ? audienceClaim : undefined,
      clientId: typeof payload.client_id === 'string' ? payload.client_id : undefined
    };
  });
});

export function resetAuthForTesting(): void {
  authClient = null;
  firebaseApp = null;
  tokenCache.clear();
  jwksCache.clear();
}
