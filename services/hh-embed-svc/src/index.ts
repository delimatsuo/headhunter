import { buildServer, getLogger } from '@hh/common';

import { getEmbeddingsServiceConfig } from './config';
import { EmbeddingsService } from './embeddings-service';
import { PgVectorClient } from './pgvector-client';
import { registerRoutes } from './routes';

async function bootstrap(): Promise<void> {
  process.env.SERVICE_NAME = process.env.SERVICE_NAME ?? 'hh-embed-svc';
  const logger = getLogger({ module: 'bootstrap' });

  try {
    logger.info('Starting hh-embed-svc bootstrap...');
    const config = getEmbeddingsServiceConfig();
    logger.info('Configuration loaded');

    const server = await buildServer({ disableDefaultHealthRoute: true });
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
    logger.info('Registering routes (with lazy dependencies)...');
    await registerRoutes(server, dependencies);
    logger.info('Routes registered');

    // Start listening IMMEDIATELY
    const port = Number(process.env.PORT ?? 8080);
    const host = '0.0.0.0';
    await server.listen({ port, host });
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
    logger.error({ error }, 'Failed to bootstrap hh-embed-svc.');
    process.exit(1);
  }
}

void bootstrap();
