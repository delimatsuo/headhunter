import 'dotenv/config';

import { buildServer, getLogger } from '@hh/common';

import { AdminService } from './admin-service';
import { getAdminServiceConfig } from './config';
import { AdminIamValidator } from './iam-validator';
import { AdminJobsClient } from './jobs-client';
import { MonitoringClient } from './monitoring-client';
import { AdminPubSubClient } from './pubsub-client';
import { registerRoutes } from './routes';

async function bootstrap(): Promise<void> {
  process.env.SERVICE_NAME = process.env.SERVICE_NAME ?? 'hh-admin-svc';

  const logger = getLogger({ module: 'admin-bootstrap' });

  try {
    logger.info('Starting hh-admin-svc bootstrap...');
    const config = getAdminServiceConfig();
    logger.info('Configuration loaded');

    // Build server immediately (no dependencies yet)
    const server = await buildServer({ disableDefaultHealthRoute: true });
    logger.info('Fastify server built');

    // Track initialization state
    let isReady = false;
    let initializationAttempts = 0;
    const MAX_INIT_ATTEMPTS = 5;

    // Initialize dependencies function (can be retried)
    const initializeDependencies = async () => {
      try {
        initializationAttempts++;
        logger.info({ attempt: initializationAttempts }, 'Initializing dependencies...');

        logger.info('Initializing Pub/Sub client...');
        const pubsubClient = new AdminPubSubClient(config.pubsub);
        logger.info('Pub/Sub client initialized');

        logger.info('Initializing Jobs client...');
        const jobsClient = new AdminJobsClient(config.jobs, config.scheduler);
        logger.info('Jobs client initialized');

        logger.info('Initializing Monitoring client...');
        const monitoringClient = new MonitoringClient(config.monitoring);
        logger.info('Monitoring client initialized');

        logger.info('Initializing IAM validator...');
        const iamValidator = new AdminIamValidator(config.iam);
        logger.info('IAM validator initialized');

        logger.info('Initializing Admin service...');
        const service = new AdminService(config, pubsubClient, jobsClient, monitoringClient);
        logger.info('Admin service initialized');

        logger.info('Registering routes...');
        await registerRoutes(server, {
          config,
          service,
          pubsub: pubsubClient,
          jobs: jobsClient,
          monitoring: monitoringClient,
          iam: iamValidator
        });
        logger.info('Routes registered');

        isReady = true;
        logger.info('hh-admin-svc fully initialized and ready');
      } catch (error) {
        logger.error({ error, attempt: initializationAttempts }, 'Failed to initialize dependencies');

        if (initializationAttempts < MAX_INIT_ATTEMPTS) {
          // Retry after delay
          const retryDelayMs = 5000 * initializationAttempts; // Exponential backoff
          logger.info({ retryDelayMs, attempt: initializationAttempts + 1 }, 'Will retry initialization...');
          setTimeout(() => {
            void initializeDependencies();
          }, retryDelayMs);
        } else {
          logger.error({ maxAttempts: MAX_INIT_ATTEMPTS }, 'Max initialization attempts reached, giving up');
        }
      }
    };

    // Register health endpoint BEFORE listening (critical for Cloud Run probes)
    server.get('/health', async () => {
      if (!isReady) {
        return { status: 'initializing', service: 'hh-admin-svc' };
      }
      return { status: 'ok', service: 'hh-admin-svc' };
    });

    // Start listening FIRST
    const port = Number(process.env.PORT ?? 8080);
    const host = '0.0.0.0';

    await server.listen({ port, host });
    logger.info({ port }, 'hh-admin-svc listening (will initialize dependencies in background)');

    // Initialize heavy dependencies in background
    setImmediate(() => {
      void initializeDependencies();
    });

    const shutdown = async () => {
      logger.info('Received shutdown signal.');
      try {
        await server.close();
        logger.info('hh-admin-svc closed gracefully.');
        process.exit(0);
      } catch (error) {
        logger.error({ error }, 'Failed to shutdown gracefully.');
        process.exit(1);
      }
    };

    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);
  } catch (error) {
    logger.error({ error }, 'Failed to bootstrap hh-admin-svc.');
    process.exit(1);
  }
}

void bootstrap();
