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

    let isReady = false;
    let redisClient: RerankRedisClient | null = null;
    let togetherClient: TogetherClient | null = null;

    const port = Number(process.env.PORT ?? 8080);
    const host = '0.0.0.0';

    await server.listen({ port, host });
    logger.info({ port }, 'hh-rerank-svc listening (initializing dependencies...)');

    server.get('/health', async () => {
      if (!isReady) {
        return { status: 'initializing' };
      }
      return { status: 'ok' };
    });


    setImmediate(async () => {
      try {
        logger.info('Initializing Redis client...');
        redisClient = new RerankRedisClient(config.redis, getLogger({ module: 'redis-client' }));
        logger.info('Redis client initialized');

        logger.info('Initializing Together AI client...');
        togetherClient = new TogetherClient(config.together, getLogger({ module: 'together-client' }));
        logger.info('Together AI client initialized');

        logger.info('Initializing rerank service...');
        const rerankService = new RerankService({
          config,
          togetherClient,
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
            const [redisHealth, togetherHealth] = await Promise.all([
              redisClient!.healthCheck(),
              togetherClient!.healthCheck()
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

        logger.info('Registering routes...');
        await registerRoutes(server, {
          service: rerankService,
          config,
          redisClient,
          togetherClient
        });
        logger.info('Routes registered');

        logger.info('Registering shutdown hooks...');
        server.addHook('onClose', async () => {
          await Promise.all([redisClient!.close(), togetherClient!.close()]);
        });
        logger.info('Shutdown hooks registered');

        isReady = true;
        logger.info('hh-rerank-svc fully initialized and ready');
      } catch (error) {
        logger.error({ error }, 'Failed to initialize dependencies');
      }
    });

    const shutdown = async () => {
      logger.info('Received shutdown signal.');
      try {
        await server.close();
        if (redisClient && togetherClient) {
          await Promise.all([redisClient.close(), togetherClient.close()]);
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
