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

    let isReady = false;
    let redisClient: EvidenceRedisClient | null = null;
    let firestoreClient: EvidenceFirestoreClient | null = null;

    // Register health endpoint BEFORE listening (critical for Cloud Run probes)
    server.get('/health', async () => {
      if (!isReady) {
        return { status: 'initializing', service: config.base.runtime.serviceName };
      }
      return { status: 'ok', service: config.base.runtime.serviceName };
    });

    const port = Number(process.env.PORT ?? 8080);
    const host = '0.0.0.0';

    await server.listen({ port, host });
    logger.info({ port, service: config.base.runtime.serviceName }, 'hh-evidence-svc listening (initializing dependencies...)');

    const initializeDependencies = async () => {
      try {
        logger.info('Initializing Redis client...');
        redisClient = new EvidenceRedisClient(config.redis, getLogger({ module: 'evidence-redis-client' }));
        logger.info('Redis client initialized');

        logger.info('Initializing Firestore client...');
        firestoreClient = new EvidenceFirestoreClient(
          getFirestore(),
          config.firestore,
          getLogger({ module: 'evidence-firestore-client' })
        );
        logger.info('Firestore client initialized');

        logger.info('Initializing evidence service...');
        const evidenceService = new EvidenceService({
          config,
          firestoreClient,
          redisClient,
          logger: getLogger({ module: 'evidence-service' })
        });
        logger.info('Evidence service initialized');

        logger.info('Registering under-pressure plugin...');
        const underPressure = await import('@fastify/under-pressure');
        await server.register(underPressure.default, {
          maxEventLoopDelay: 2000,
          maxHeapUsedBytes: 1_024 * 1_024 * 1024,
          maxRssBytes: 1_536 * 1_024 * 1024,
          healthCheckInterval: 10000,
          healthCheck: async () => {
            if (!redisClient || !firestoreClient) return true;

            const [redis, firestore] = await Promise.all([
              redisClient.healthCheck(),
              firestoreClient.healthCheck()
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

        logger.info('Registering routes...');
        await registerRoutes(server, {
          service: evidenceService,
          config,
          redisClient,
          firestoreClient
        });
        logger.info('Routes registered');

        server.addHook('onClose', async () => {
          if (redisClient) {
            await redisClient.close();
          }
        });

        isReady = true;
        logger.info('hh-evidence-svc fully initialized and ready');
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
        if (redisClient) {
          await redisClient.close();
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
