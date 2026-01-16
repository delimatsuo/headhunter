import fastify, { type FastifyInstance } from 'fastify';

import { authenticationPlugin } from './auth';
import { getConfig } from './config';
import { errorHandlerPlugin } from './errors';
import { getLogger } from './logger';
import { requestLoggingPlugin } from './logger';
import { tenantValidationPlugin } from './tenant';

export interface BuildServerOptions {
  disableAuth?: boolean;
  disableTenantValidation?: boolean;
  disableDefaultHealthRoute?: boolean;
  disableRateLimit?: boolean;
}

export async function buildServer(options: BuildServerOptions = {}): Promise<FastifyInstance> {
  const config = getConfig();
  const helmet = await import('@fastify/helmet');
  const cors = await import('@fastify/cors');

  const app = fastify({
    logger: true,
    disableRequestLogging: true,
    trustProxy: true
  });

  await app.register(requestLoggingPlugin);
  await app.register(errorHandlerPlugin);

  if (!options.disableAuth) {
    await app.register(authenticationPlugin);
  }

  if (!options.disableTenantValidation) {
    await app.register(tenantValidationPlugin);
  }

  await app.register(helmet.default, { global: true });
  await app.register(cors.default, {
    origin: config.cors.allowedOrigins,
    credentials: config.cors.credentials
  });

  // Rate limiting for defense in depth (in addition to API Gateway limits)
  if (!options.disableRateLimit) {
    const rateLimit = await import('@fastify/rate-limit');
    const logger = getLogger({ module: 'rate-limit' });

    await app.register(rateLimit.default, {
      max: config.rateLimits.globalRps,
      timeWindow: '1 second',
      keyGenerator: (request) => {
        // Use tenant ID if available, otherwise fall back to IP
        return request.tenant?.id ?? request.ip;
      },
      errorResponseBuilder: () => ({
        code: 'rate_limited',
        message: 'Too many requests. Please slow down.',
        details: { retryAfter: '1 second' }
      }),
      onExceeded: (request) => {
        logger.warn({
          tenantId: request.tenant?.id,
          ip: request.ip,
          path: request.url
        }, 'Rate limit exceeded');
      }
    });
  }

  if (!options.disableDefaultHealthRoute) {
    app.get('/health', async () => ({
      status: 'ok',
      service: config.runtime.serviceName
    }));
  }

  app.get('/ready', async () => ({
    status: 'ready',
    service: config.runtime.serviceName
  }));

  app.addHook('onClose', async () => {
    // Placeholder for future resource cleanup hooks
  });

  return app;
}
