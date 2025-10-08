import { buildServer, getLogger, getFirestore } from '@hh/common';

import { EmbedClient } from './embed-client';
import { getSearchServiceConfig } from './config';
import { PgVectorClient } from './pgvector-client';
import { registerRoutes } from './routes';
import { SearchRedisClient } from './redis-client';
import { SearchService } from './search-service';
import { RerankClient } from './rerank-client';
import { PerformanceTracker } from './performance-tracker';

async function bootstrap(): Promise<void> {
  process.env.SERVICE_NAME = process.env.SERVICE_NAME ?? 'hh-search-svc';
  const logger = getLogger({ module: 'bootstrap' });

  try {
    logger.info('Starting hh-search-svc bootstrap...');

    const config = getSearchServiceConfig();
    logger.info({ serviceName: config.base.runtime.serviceName }, 'Configuration loaded');

    const server = await buildServer({ disableDefaultHealthRoute: true });
    logger.info('Fastify server built');

    const performanceTracker = new PerformanceTracker();

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
      rerankClient: null as RerankClient | null,
      performanceTracker,
      state  // Pass state to routes
    };

    // Register ALL routes BEFORE listen (required by Fastify)
    // Routes will use lazily-initialized dependencies via closure
    logger.info('Registering routes (with lazy dependencies)...');
    await registerRoutes(server, dependencies);
    logger.info('Routes registered');

    // Register under-pressure plugin BEFORE listen (required by Fastify)
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

    // Register cleanup hook BEFORE listen (required by Fastify)
    server.addHook('onClose', async () => {
      if (dependencies.pgClient && dependencies.redisClient) {
        await Promise.all([dependencies.pgClient.close(), dependencies.redisClient.close()]);
      }
    });

    // Start listening IMMEDIATELY (Cloud Run requires fast startup)
    const port = Number(process.env.PORT ?? 8080);
    const host = '0.0.0.0';
    await server.listen({ port, host });
    logger.info({ port, service: config.base.runtime.serviceName }, 'hh-search-svc listening (initializing dependencies...)');

    // Initialize real dependencies in background (after listen)
    setImmediate(async () => {
      let pgClient: PgVectorClient | null = null;
      let redisClient: SearchRedisClient | null = null;
      let embedClient: EmbedClient | null = null;
      let rerankClient: RerankClient | null = null;

      try {
        logger.info('Initializing pgvector client...');
        pgClient = new PgVectorClient(config.pgvector, getLogger({ module: 'pgvector-client' }));
        await pgClient.initialize();
        dependencies.pgClient = pgClient;
        logger.info('pgvector client initialized');

        logger.info('Initializing Redis client...');
        redisClient = new SearchRedisClient(config.redis, getLogger({ module: 'redis-client' }));
        dependencies.redisClient = redisClient;
        logger.info('Redis client initialized');

        logger.info('Initializing embed client...');
        embedClient = new EmbedClient(config.embed, getLogger({ module: 'embed-client' }));
        dependencies.embedClient = embedClient;
        logger.info('Embed client initialized');

        if (config.rerank.enabled) {
          logger.info('Initializing rerank client...');
          rerankClient = new RerankClient(config.rerank, getLogger({ module: 'rerank-client' }));
          dependencies.rerankClient = rerankClient;
          logger.info('Rerank client initialized');
        } else {
          logger.info('Rerank disabled via configuration.');
        }

        logger.info('Initializing search service...');
        dependencies.service = new SearchService({
          config,
          pgClient: dependencies.pgClient,
          embedClient: dependencies.embedClient,
          redisClient: dependencies.redisClient ?? undefined,
          rerankClient: dependencies.rerankClient ?? undefined,
          performanceTracker,
          logger: getLogger({ module: 'search-service' })
        });

        if (config.firestoreFallback.enabled) {
          dependencies.service.setFirestore(getFirestore());
        }
        logger.info('Search service initialized');

        state.isReady = true;
        logger.info('hh-search-svc fully initialized and ready');
      } catch (error) {
        const errorDetails = error instanceof Error
          ? { name: error.name, message: error.message, stack: error.stack }
          : { raw: String(error) };
        logger.error({ error: errorDetails }, 'Failed to initialize dependencies - service running in degraded mode');
        // Clean up any partially initialized resources
        if (pgClient && !dependencies.pgClient) {
          await pgClient.close().catch(() => {});
        }
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
