import { buildServer, getLogger, getFirestore } from '@hh/common';

import { EmbedClient } from './embed-client';
import { getSearchServiceConfig } from './config';
import { PgVectorClient } from './pgvector-client';
import { registerRoutes } from './routes';
import { SearchRedisClient } from './redis-client';
import { SearchService } from './search-service';

async function bootstrap(): Promise<void> {
  process.env.SERVICE_NAME = process.env.SERVICE_NAME ?? 'hh-search-svc';
  const logger = getLogger({ module: 'bootstrap' });

  try {
    logger.info('Starting hh-search-svc bootstrap...');

    const config = getSearchServiceConfig();
    logger.info({ serviceName: config.base.runtime.serviceName }, 'Configuration loaded');

    const server = await buildServer({ disableDefaultHealthRoute: true });
    logger.info('Fastify server built');

    // Track initialization state with mutable dependency container
    const state = {
      isReady: false
    };
    const dependencies = {
      config,
      service: null as SearchService | null,
      redisClient: null as SearchRedisClient | null,
      pgClient: null as PgVectorClient | null,
      embedClient: null as EmbedClient | null,
      state  // Pass state to routes
    };

    // Register ALL routes BEFORE listen (required by Fastify)
    // Routes will use lazily-initialized dependencies via closure
    logger.info('Registering routes (with lazy dependencies)...');
    await registerRoutes(server, dependencies);
    logger.info('Routes registered');

    // Start listening IMMEDIATELY (Cloud Run requires fast startup)
    const port = Number(process.env.PORT ?? 8080);
    const host = '0.0.0.0';
    await server.listen({ port, host });
    logger.info({ port, service: config.base.runtime.serviceName }, 'hh-search-svc listening (initializing dependencies...)');

    // Initialize real dependencies in background (after listen)
    setImmediate(async () => {
      try {
        logger.info('Initializing pgvector client...');
        dependencies.pgClient = new PgVectorClient(config.pgvector, getLogger({ module: 'pgvector-client' }));
        await dependencies.pgClient.initialize();
        logger.info('pgvector client initialized');

        logger.info('Initializing Redis client...');
        dependencies.redisClient = new SearchRedisClient(config.redis, getLogger({ module: 'redis-client' }));
        logger.info('Redis client initialized');

        logger.info('Initializing embed client...');
        dependencies.embedClient = new EmbedClient(config.embed, getLogger({ module: 'embed-client' }));
        logger.info('Embed client initialized');

        logger.info('Initializing search service...');
        dependencies.service = new SearchService({
          config,
          pgClient: dependencies.pgClient,
          embedClient: dependencies.embedClient,
          logger: getLogger({ module: 'search-service' })
        });

        if (config.firestoreFallback.enabled) {
          dependencies.service.setFirestore(getFirestore());
        }
        logger.info('Search service initialized');

        logger.info('Registering under-pressure plugin...');
        const underPressure = await import('@fastify/under-pressure');
        await server.register(underPressure.default, {
          maxEventLoopDelay: 2000,
          maxHeapUsedBytes: 1_024 * 1_024 * 1024,
          maxRssBytes: 1_536 * 1_024 * 1024,
          healthCheck: async () => {
            if (!dependencies.pgClient) return true;
            const health = await dependencies.pgClient.healthCheck();
            if (health.status !== 'healthy') {
              throw new Error(health.message ?? 'pgvector degraded');
            }
            return true;
          },
          healthCheckInterval: 10000
        });
        logger.info('Under-pressure plugin registered');

        server.addHook('onClose', async () => {
          if (dependencies.pgClient && dependencies.redisClient) {
            await Promise.all([dependencies.pgClient.close(), dependencies.redisClient.close()]);
          }
        });

        state.isReady = true;
        logger.info('hh-search-svc fully initialized and ready');
      } catch (error) {
        logger.error({ error }, 'Failed to initialize dependencies - service running in degraded mode');
        // Service stays up but routes will fail when accessed
      }
    });

    const shutdown = async () => {
      logger.info('Received shutdown signal.');
      try {
        await server.close();
        if (dependencies.pgClient && dependencies.redisClient) {
          await Promise.all([dependencies.pgClient.close(), dependencies.redisClient.close()]);
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
    logger.error({ error }, 'Failed to bootstrap hh-search-svc');
    process.exit(1);
  }
}

void bootstrap();
