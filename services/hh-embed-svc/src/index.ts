import { buildServer, getLogger } from '@hh/common';

import { getEmbeddingsServiceConfig } from './config';
import { EmbeddingsService } from './embeddings-service';
import { PgVectorClient } from './pgvector-client';
import { registerRoutes } from './routes';

async function bootstrap(): Promise<void> {
  console.log('[BOOTSTRAP] Starting bootstrap function');
  process.env.SERVICE_NAME = process.env.SERVICE_NAME ?? 'hh-embed-svc';

  console.log('[BOOTSTRAP] Getting logger');
  const logger = getLogger({ module: 'bootstrap' });

  try {
    console.log('[BOOTSTRAP] Logger initialized, starting bootstrap');
    logger.info('Starting hh-embed-svc bootstrap...');
    console.log('[BOOTSTRAP] Getting config');
    const config = getEmbeddingsServiceConfig();
    console.log('[BOOTSTRAP] Config loaded');
    logger.info('Configuration loaded');

    console.log('[BOOTSTRAP] Building server');
    const server = await buildServer({ disableDefaultHealthRoute: true });
    console.log('[BOOTSTRAP] Server built');
    logger.info('Fastify server built');

    // Mutable dependency container - routes will reference this object
    const state = { isReady: false };
    const dependencies = {
      config,
      pgClient: null as PgVectorClient | null,
      service: null as EmbeddingsService | null,
      state
    };

    // Register ALL routes BEFORE listen (required by Fastify)
    console.log('[BOOTSTRAP] About to register routes');
    logger.info('Registering routes (with lazy dependencies)...');
    await registerRoutes(server, dependencies);
    console.log('[BOOTSTRAP] Routes registered successfully');
    console.log('[BOOTSTRAP] Fastify routes:', JSON.stringify(server.printRoutes()));
    logger.info('Routes registered');

    // Start listening IMMEDIATELY
    const port = Number(process.env.PORT ?? 8080);
    const host = '0.0.0.0';
    console.log(`[BOOTSTRAP] About to listen on ${host}:${port}`);
    await server.listen({ port, host });
    console.log(`[BOOTSTRAP] Server listening on ${host}:${port}`);
    logger.info({ port }, 'hh-embed-svc listening (initializing dependencies...)');

    // Initialize real dependencies in background (after listen)
    setImmediate(async () => {
      try {
        logger.info('Initializing pgvector client...');
        dependencies.pgClient = new PgVectorClient(config.pgvector, getLogger({ module: 'pgvector-client' }));
        await dependencies.pgClient.initialize();
        logger.info('pgvector client initialized');

        logger.info('Initializing embeddings service...');
        dependencies.service = new EmbeddingsService({
          config,
          pgClient: dependencies.pgClient,
          logger: getLogger({ module: 'embeddings-service' })
        });
        logger.info('Embeddings service initialized');

        server.addHook('onClose', async () => {
          if (dependencies.pgClient) {
            await dependencies.pgClient.close();
          }
        });

        state.isReady = true;
        logger.info('hh-embed-svc fully initialized and ready');
      } catch (error) {
        logger.error({ error }, 'Failed to initialize dependencies - service running in degraded mode');
      }
    });

    const shutdown = async () => {
      logger.info('Received shutdown signal.');
      try {
        await server.close();
        if (dependencies.pgClient) {
          await dependencies.pgClient.close();
        }
        logger.info('Server closed gracefully.');
        process.exit(0);
      } catch (error) {
        logger.error({ error }, 'Failed to close server gracefully.');
        process.exit(1);
      }
    };

    process.on('SIGTERM', shutdown);
    process.on('SIGINT', shutdown);
  } catch (error) {
    console.error('[BOOTSTRAP] ERROR:', error);
    logger.error({ error }, 'Failed to bootstrap hh-embed-svc.');
    process.exit(1);
  }
}

console.log('[MAIN] About to call bootstrap');
void bootstrap();
console.log('[MAIN] Bootstrap called');
