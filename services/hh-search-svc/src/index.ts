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

    let isReady = false;
    let pgClient: PgVectorClient | null = null;
    let redisClient: SearchRedisClient | null = null;

    // Register health endpoints BEFORE listening (critical for Cloud Run probes)
    server.get('/health', async () => {
      if (!isReady) {
        return { status: 'initializing', service: config.base.runtime.serviceName };
      }
      return { status: 'ok', service: config.base.runtime.serviceName };
    });
    logger.debug('Health endpoint registered');

    // Note: /ready endpoint is already registered by buildServer in @hh/common

    // Start listening AFTER registering health endpoints
    const port = Number(process.env.PORT ?? 8080);
    const host = '0.0.0.0';

    await server.listen({ port, host });
    logger.info({ port, service: config.base.runtime.serviceName }, 'hh-search-svc listening (initializing dependencies...)');

    const initializeDependencies = async () => {
      try {
        logger.info('Initializing pgvector client...');
        pgClient = new PgVectorClient(config.pgvector, getLogger({ module: 'pgvector-client' }));
        await pgClient.initialize();
        logger.info('pgvector client initialized');

        logger.info('Initializing Redis client...');
        redisClient = new SearchRedisClient(config.redis, getLogger({ module: 'redis-client' }));
        logger.info('Redis client initialized');

        logger.info('Initializing embed client...');
        const embedClient = new EmbedClient(config.embed, getLogger({ module: 'embed-client' }));
        logger.info('Embed client initialized');

        logger.info('Initializing search service...');
        const searchService = new SearchService({
          config,
          pgClient,
          embedClient,
          logger: getLogger({ module: 'search-service' })
        });

        if (config.firestoreFallback.enabled) {
          searchService.setFirestore(getFirestore());
        }
        logger.info('Search service initialized');

        logger.info('Registering under-pressure plugin...');
        const underPressure = await import('@fastify/under-pressure');
        await server.register(underPressure.default, {
          maxEventLoopDelay: 2000,
          maxHeapUsedBytes: 1_024 * 1_024 * 1024,
          maxRssBytes: 1_536 * 1_024 * 1024,
          healthCheck: async () => {
            if (!pgClient) return true;
            const health = await pgClient.healthCheck();
            if (health.status !== 'healthy') {
              throw new Error(health.message ?? 'pgvector degraded');
            }
            return true;
          },
          healthCheckInterval: 10000
        });
        logger.info('Under-pressure plugin registered');

        logger.info('Registering routes...');
        await registerRoutes(server, {
          service: searchService,
          config,
          redisClient,
          pgClient,
          embedClient
        });
        logger.info('Routes registered');

        server.addHook('onClose', async () => {
          if (pgClient && redisClient) {
            await Promise.all([pgClient.close(), redisClient.close()]);
          }
        });

        isReady = true;
        logger.info('hh-search-svc fully initialized and ready');
      } catch (error) {
        logger.error({ error }, 'Failed to initialize dependencies, will retry in 5 seconds...');
        setTimeout(() => {
          logger.info('Retrying dependency initialization...');
          void initializeDependencies();
        }, 5000);
      }
    };

    setImmediate(() => {
      void initializeDependencies();
    });

    const shutdown = async () => {
      logger.info('Received shutdown signal.');
      try {
        await server.close();
        if (pgClient && redisClient) {
          await Promise.all([pgClient.close(), redisClient.close()]);
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
