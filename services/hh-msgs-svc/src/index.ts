import { buildServer, getLogger } from '@hh/common';

import { getMsgsServiceConfig } from './config';
import { MsgsCloudSqlClient } from './cloudsql-client';
import { MsgsRedisClient } from './redis-client';
import { MsgsService } from './msgs-service';
import { registerRoutes } from './routes';

async function bootstrap(): Promise<void> {
  process.env.SERVICE_NAME = process.env.SERVICE_NAME ?? 'hh-msgs-svc';

  const logger = getLogger({ module: 'msgs-bootstrap' });

  try {
    logger.info('Starting hh-msgs-svc bootstrap...');
    const config = getMsgsServiceConfig();
    logger.info('Configuration loaded');

    const server = await buildServer({ disableDefaultHealthRoute: true });
    logger.info('Fastify server built');

    // Track initialization state with mutable dependency container
    const state = {
      isReady: false
    };
    const dependencies = {
      config,
      service: null as MsgsService | null,
      redisClient: null as MsgsRedisClient | null,
      cloudSqlClient: null as MsgsCloudSqlClient | null,
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
    logger.info({ port, service: config.base.runtime.serviceName }, 'hh-msgs-svc listening (initializing dependencies...)');

    // Initialize real dependencies in background (after listen)
    setImmediate(async () => {
      try {
        logger.info('Initializing Redis client...');
        dependencies.redisClient = new MsgsRedisClient(config.redis, getLogger({ module: 'msgs-redis-client' }));
        logger.info('Redis client initialized');

        logger.info('Initializing Cloud SQL client...');
        dependencies.cloudSqlClient = new MsgsCloudSqlClient(
          config.database,
          getLogger({ module: 'msgs-cloudsql-client' })
        );
        logger.info('Cloud SQL client initialized');

        logger.info('Initializing msgs service...');
        dependencies.service = new MsgsService({
          config,
          redisClient: dependencies.redisClient,
          dbClient: dependencies.cloudSqlClient,
          logger: getLogger({ module: 'msgs-service' })
        });
        logger.info('Msgs service initialized');

        logger.info('Registering under-pressure plugin...');
        const underPressure = await import('@fastify/under-pressure');
        await server.register(underPressure.default, {
          maxEventLoopDelay: 2000,
          maxHeapUsedBytes: 1_024 * 1_024 * 1024,
          maxRssBytes: 1_536 * 1_024 * 1024,
          healthCheckInterval: 10000,
          healthCheck: async () => {
            if (!dependencies.redisClient || !dependencies.cloudSqlClient) return true;

            const [redis, cloudSql] = await Promise.all([
              dependencies.redisClient.healthCheck(),
              dependencies.cloudSqlClient.healthCheck()
            ]);

            if (!['healthy', 'disabled'].includes(redis.status)) {
              throw new Error(redis.message ?? 'Redis degraded.');
            }

            if (cloudSql.status !== 'healthy' && !config.runtime.useSeedData) {
              throw new Error(cloudSql.message ?? 'Cloud SQL degraded.');
            }

            if (cloudSql.status !== 'healthy' && config.runtime.useSeedData) {
              logger.warn(
                { status: cloudSql.status, message: cloudSql.message },
                'Cloud SQL unreachable in seed mode.'
              );
            }

            return true;
          }
        });
        logger.info('Under-pressure plugin registered');

        server.addHook('onClose', async () => {
          if (dependencies.redisClient && dependencies.cloudSqlClient) {
            await Promise.all([dependencies.redisClient.close(), dependencies.cloudSqlClient.close()]);
          }
        });

        state.isReady = true;
        logger.info('hh-msgs-svc fully initialized and ready');
      } catch (error) {
        logger.error({ error }, 'Failed to initialize dependencies - service running in degraded mode');
        // Service stays up but routes will fail when accessed
      }
    });

    const shutdown = async () => {
      logger.info('Received shutdown signal.');
      try {
        await server.close();
        if (dependencies.redisClient && dependencies.cloudSqlClient) {
          await Promise.all([dependencies.redisClient.close(), dependencies.cloudSqlClient.close()]);
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
    logger.error({ error }, 'Failed to bootstrap hh-msgs-svc.');
    process.exit(1);
  }
}

void bootstrap();
