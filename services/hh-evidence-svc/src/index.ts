import { buildServer, getFirestore, getLogger } from '@hh/common';

import { getEvidenceServiceConfig } from './config';
import { EvidenceFirestoreClient } from './firestore-client';
import { EvidenceRedisClient } from './redis-client';
import { EvidenceService } from './evidence-service';
import { registerRoutes } from './routes';

async function bootstrap(): Promise<void> {
  process.env.SERVICE_NAME = process.env.SERVICE_NAME ?? 'hh-evidence-svc';

  const logger = getLogger({ module: 'evidence-bootstrap' });

  try {
    logger.info('Starting hh-evidence-svc bootstrap...');
    const config = getEvidenceServiceConfig();
    logger.info('Configuration loaded');

    const server = await buildServer({ disableDefaultHealthRoute: true });
    logger.info('Fastify server built');

    // Track initialization state with mutable dependency container
    const state = {
      isReady: false
    };
    const dependencies = {
      config,
      service: null as EvidenceService | null,
      redisClient: null as EvidenceRedisClient | null,
      firestoreClient: null as EvidenceFirestoreClient | null,
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

    // Register cleanup hook BEFORE listen (required by Fastify)
    server.addHook('onClose', async () => {
      if (dependencies.redisClient) {
        await dependencies.redisClient.close();
      }
    });

    // Start listening IMMEDIATELY (Cloud Run requires fast startup)
    const port = Number(process.env.PORT ?? 8080);
    const host = '0.0.0.0';
    await server.listen({ port, host });
    logger.info({ port, service: config.base.runtime.serviceName }, 'hh-evidence-svc listening (initializing dependencies...)');

    // Initialize real dependencies in background (after listen)
    setImmediate(async () => {
      try {
        logger.info('Initializing Redis client...');
        dependencies.redisClient = new EvidenceRedisClient(config.redis, getLogger({ module: 'evidence-redis-client' }));
        logger.info('Redis client initialized');

        logger.info('Initializing Firestore client...');
        dependencies.firestoreClient = new EvidenceFirestoreClient(
          getFirestore(),
          config.firestore,
          getLogger({ module: 'evidence-firestore-client' })
        );
        logger.info('Firestore client initialized');

        logger.info('Initializing evidence service...');
        dependencies.service = new EvidenceService({
          config,
          firestoreClient: dependencies.firestoreClient,
          redisClient: dependencies.redisClient,
          logger: getLogger({ module: 'evidence-service' })
        });
        logger.info('Evidence service initialized');

        state.isReady = true;
        logger.info('hh-evidence-svc fully initialized and ready');
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
    logger.error({ error }, 'Failed to bootstrap hh-evidence-svc.');
    process.exit(1);
  }
}

void bootstrap();
