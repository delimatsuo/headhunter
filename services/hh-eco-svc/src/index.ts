import { buildServer, getFirestore, getLogger } from '@hh/common';

import { getEcoServiceConfig } from './config.js';
import { EcoRedisClient } from './redis-client.js';
import { EcoFirestoreClient } from './firestore-client.js';
import { EcoService } from './eco-service.js';
import { registerRoutes } from './routes.js';

async function bootstrap(): Promise<void> {
  process.env.SERVICE_NAME = process.env.SERVICE_NAME ?? 'hh-eco-svc';

  const logger = getLogger({ module: 'bootstrap' });

  try {
    logger.info('Starting hh-eco-svc bootstrap...');
    const config = getEcoServiceConfig();
    logger.info('Configuration loaded');

    const server = await buildServer({ disableDefaultHealthRoute: true });
    logger.info('Fastify server built');

    // Track initialization state with mutable dependency container
    const state = {
      isReady: false
    };
    const dependencies = {
      config,
      service: null as EcoService | null,
      redisClient: null as EcoRedisClient | null,
      firestoreClient: null as EcoFirestoreClient | null,
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
    logger.info({ port, service: config.base.runtime.serviceName }, 'hh-eco-svc listening (initializing dependencies...)');

    // Initialize real dependencies in background (after listen)
    setImmediate(async () => {
      try {
        logger.info('Initializing Redis client...');
        dependencies.redisClient = new EcoRedisClient(config.redis, getLogger({ module: 'redis-client' }));
        logger.info('Redis client initialized');

        logger.info('Initializing Firestore client...');
        dependencies.firestoreClient = new EcoFirestoreClient(
          getFirestore(),
          config.firestore,
          getLogger({ module: 'firestore-client' })
        );
        logger.info('Firestore client initialized');

        logger.info('Initializing ECO service...');
        dependencies.service = new EcoService({
          config,
          firestoreClient: dependencies.firestoreClient,
          redisClient: dependencies.redisClient,
          logger: getLogger({ module: 'eco-service' })
        });
        logger.info('ECO service initialized');

        logger.info('Registering under-pressure plugin...');
        const underPressure = await import('@fastify/under-pressure');
        await server.register(underPressure.default, {
          maxEventLoopDelay: 2000,
          maxHeapUsedBytes: 1_024 * 1_024 * 1024,
          maxRssBytes: 1_536 * 1_024 * 1024,
          healthCheckInterval: 10000,
          healthCheck: async () => {
            if (!dependencies.redisClient || !dependencies.firestoreClient) return true;
            const [redis, firestore] = await Promise.all([
              dependencies.redisClient.healthCheck(),
              dependencies.firestoreClient.healthCheck()
            ]);

            if (!['healthy', 'disabled'].includes(redis.status)) {
              throw new Error(redis.message ?? 'Redis degraded.');
            }

            if (firestore.status !== 'healthy') {
              throw new Error(firestore.message ?? 'Firestore degraded.');
            }
            return true;
          }
        });
        logger.info('Under-pressure plugin registered');

        server.addHook('onClose', async () => {
          if (dependencies.redisClient) {
            await dependencies.redisClient.close();
          }
        });

        state.isReady = true;
        logger.info('hh-eco-svc fully initialized and ready');
      } catch (error) {
        logger.error({ error }, 'Failed to initialize dependencies - service running in degraded mode');
        // Service stays up but routes will fail when accessed
      }
    });

    const shutdown = async () => {
      logger.info('Received shutdown signal.');
      try {
        await server.close();
        if (dependencies.redisClient) {
          await dependencies.redisClient.close();
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
    logger.error({ error }, 'Failed to bootstrap hh-eco-svc.');
    process.exit(1);
  }
}

void bootstrap();
