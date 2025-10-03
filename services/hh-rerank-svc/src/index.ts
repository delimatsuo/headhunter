import { buildServer, getLogger } from '@hh/common';

import { getRerankServiceConfig } from './config.js';
import { registerRoutes } from './routes.js';
import { RerankRedisClient } from './redis-client.js';
import { RerankService } from './rerank-service.js';
import { TogetherClient } from './together-client.js';

async function bootstrap(): Promise<void> {
  process.env.SERVICE_NAME = process.env.SERVICE_NAME ?? 'hh-rerank-svc';

  const logger = getLogger({ module: 'rerank-bootstrap' });

  try {
    logger.info('Starting hh-rerank-svc bootstrap...');
    const config = getRerankServiceConfig();
    logger.info('Configuration loaded');

    const server = await buildServer({ disableDefaultHealthRoute: true });
    logger.info('Fastify server built');

    // Track initialization state with mutable dependency container
    const state = {
      isReady: false
    };
    const dependencies = {
      config,
      service: null as RerankService | null,
      redisClient: null as RerankRedisClient | null,
      togetherClient: null as TogetherClient | null,
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
    logger.info({ port }, 'hh-rerank-svc listening (initializing dependencies...)');

    // Initialize real dependencies in background (after listen)
    setImmediate(async () => {
      try {
        logger.info('Initializing Redis client...');
        dependencies.redisClient = new RerankRedisClient(config.redis, getLogger({ module: 'redis-client' }));
        logger.info('Redis client initialized');

        logger.info('Initializing Together AI client...');
        dependencies.togetherClient = new TogetherClient(config.together, getLogger({ module: 'together-client' }));
        logger.info('Together AI client initialized');

        logger.info('Initializing rerank service...');
        dependencies.service = new RerankService({
          config,
          togetherClient: dependencies.togetherClient,
          logger: getLogger({ module: 'rerank-service' })
        });
        logger.info('Rerank service initialized');

        logger.info('Registering under-pressure plugin...');
        const underPressure = await import('@fastify/under-pressure');
        await server.register(underPressure.default, {
          maxEventLoopDelay: 1500,
          maxHeapUsedBytes: 1_024 * 1_024 * 1024,
          maxRssBytes: 1_536 * 1_024 * 1024,
          healthCheck: async () => {
            if (!dependencies.redisClient || !dependencies.togetherClient) return true;

            const [redisHealth, togetherHealth] = await Promise.all([
              dependencies.redisClient.healthCheck(),
              dependencies.togetherClient.healthCheck()
            ]);

            const unhealthy = [];
            if (!['healthy', 'disabled'].includes(redisHealth.status)) {
              unhealthy.push('redis');
            }
            if (!['healthy', 'disabled'].includes(togetherHealth.status)) {
              unhealthy.push('together');
            }

            if (unhealthy.length > 0) {
              throw new Error(`Dependent services degraded: ${unhealthy.join(', ')}`);
            }

            return true;
          },
          healthCheckInterval: 10000
        });
        logger.info('Under-pressure plugin registered');

        logger.info('Registering shutdown hooks...');
        server.addHook('onClose', async () => {
          if (dependencies.redisClient && dependencies.togetherClient) {
            await Promise.all([dependencies.redisClient.close(), dependencies.togetherClient.close()]);
          }
        });
        logger.info('Shutdown hooks registered');

        state.isReady = true;
        logger.info('hh-rerank-svc fully initialized and ready');
      } catch (error) {
        logger.error({ error }, 'Failed to initialize dependencies - service running in degraded mode');
        // Service stays up but routes will fail when accessed
      }
    });

    const shutdown = async () => {
      logger.info('Received shutdown signal.');
      try {
        await server.close();
        if (dependencies.redisClient && dependencies.togetherClient) {
          await Promise.all([dependencies.redisClient.close(), dependencies.togetherClient.close()]);
        }
        logger.info('hh-rerank-svc closed gracefully.');
        process.exit(0);
      } catch (error) {
        logger.error({ error }, 'Failed to shutdown gracefully.');
        process.exit(1);
      }
    };

    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);
  } catch (error) {
    logger.error({ error }, 'Failed to bootstrap hh-rerank-svc.');
    process.exit(1);
  }
}

void bootstrap();
