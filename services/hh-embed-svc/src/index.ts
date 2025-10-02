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

    // Build server immediately (no dependencies yet)
    const server = await buildServer({ disableDefaultHealthRoute: true });
    logger.info('Fastify server built');

    // Track initialization state
    let isReady = false;
    let pgClient: PgVectorClient | null = null;
    let embeddingsService: EmbeddingsService | null = null;

    // Register health endpoints BEFORE listening (critical for Cloud Run probes)
    server.get('/health', async () => {
      if (!isReady) {
        return { status: 'initializing', service: config.base.runtime.serviceName };
      }
      return { status: 'ok', service: config.base.runtime.serviceName };
    });

    // Note: /ready endpoint is already registered by buildServer in @hh/common

    // Start listening AFTER registering health endpoints
    const port = Number(process.env.PORT ?? 8080);
    const host = '0.0.0.0';

    await server.listen({ port, host });
    logger.info({ port, service: config.base.runtime.serviceName }, 'hh-embed-svc listening (initializing dependencies...)');

    // Initialize heavy dependencies in background
    setImmediate(async () => {
      try {
        logger.info('Initializing pgvector client...');
        pgClient = new PgVectorClient(config.pgvector, getLogger({ module: 'pgvector-client' }));
        await pgClient.initialize();
        logger.info('pgvector client initialized');

        logger.info('Initializing embeddings service...');
        embeddingsService = new EmbeddingsService({
          config,
          pgClient,
          logger: getLogger({ module: 'embeddings-service' })
        });
        logger.info('Embeddings service initialized');

        logger.info('Registering routes...');
        await registerRoutes(server, { service: embeddingsService, config, pgClient });
        logger.info('Routes registered');

        server.addHook('onClose', async () => {
          if (pgClient) {
            await pgClient.close();
          }
        });

        isReady = true;
        logger.info('hh-embed-svc fully initialized and ready');
      } catch (error) {
        logger.error({ error }, 'Failed to initialize dependencies');
        // Don't exit - server is still running and can report errors via /health
        // Retry initialization after a delay
        setTimeout(() => {
          logger.info('Retrying initialization...');
          void bootstrap();
        }, 5000);
      }
    });

    const shutdown = async () => {
      logger.info('Received shutdown signal.');
      try {
        await server.close();
        if (pgClient) {
          await pgClient.close();
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
