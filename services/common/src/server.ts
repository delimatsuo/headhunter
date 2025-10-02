import fastify, { type FastifyInstance } from 'fastify';

import { authenticationPlugin } from './auth';
import { getConfig } from './config';
import { errorHandlerPlugin } from './errors';
import { requestLoggingPlugin } from './logger';
import { tenantValidationPlugin } from './tenant';

export interface BuildServerOptions {
  disableAuth?: boolean;
  disableTenantValidation?: boolean;
  disableDefaultHealthRoute?: boolean;
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
    origin: true
  });

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
