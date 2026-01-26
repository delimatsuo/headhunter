import 'dotenv/config';

import { Pool } from 'pg';
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

    // Track initialization state with mutable dependency container
    const state = {
      isReady: false
    };
    const dependencies = {
      config,
      service: null as any,
      pubsub: null as any,
      jobs: null as any,
      monitoring: null as any,
      iam: null as any,
      pgPool: undefined as Pool | undefined,
      state  // Pass state to routes
    };

    // Register ALL routes BEFORE listen (required by Fastify)
    // Routes will use lazily-initialized dependencies via closure
    // Routes module includes /health endpoint
    logger.info('Registering routes (with lazy dependencies)...');
    await registerRoutes(server, dependencies);
    logger.info('Routes registered');

    // Start listening IMMEDIATELY (Cloud Run requires fast startup)
    const port = Number(process.env.PORT ?? 8080);
    const host = '0.0.0.0';
    await server.listen({ port, host });
    logger.info({ port }, 'hh-admin-svc listening (initializing dependencies...)');

    // Initialize real dependencies in background (after listen)
    setImmediate(async () => {
      try {
        logger.info('Initializing Pub/Sub client...');
        dependencies.pubsub = new AdminPubSubClient(config.pubsub);
        logger.info('Pub/Sub client initialized');

        logger.info('Initializing Jobs client...');
        dependencies.jobs = new AdminJobsClient(config.jobs, config.scheduler);
        logger.info('Jobs client initialized');

        logger.info('Initializing Monitoring client...');
        dependencies.monitoring = new MonitoringClient(config.monitoring);
        logger.info('Monitoring client initialized');

        logger.info('Initializing IAM validator...');
        dependencies.iam = new AdminIamValidator(config.iam);
        logger.info('IAM validator initialized');

        logger.info('Initializing Admin service...');
        dependencies.service = new AdminService(config, dependencies.pubsub, dependencies.jobs, dependencies.monitoring);
        logger.info('Admin service initialized');

        // Initialize PostgreSQL pool for bias metrics (optional - continues if fails)
        try {
          logger.info('Initializing PostgreSQL pool for bias metrics...');
          dependencies.pgPool = new Pool({
            host: config.pg.host,
            port: config.pg.port,
            database: config.pg.database,
            user: config.pg.user,
            password: config.pg.password,
            ssl: config.pg.ssl ? { rejectUnauthorized: false } : false,
            max: config.pg.poolMax,
            min: config.pg.poolMin,
            idleTimeoutMillis: config.pg.idleTimeoutMs,
            connectionTimeoutMillis: config.pg.connectionTimeoutMs
          });
          // Test connection
          await dependencies.pgPool.query('SELECT 1');
          logger.info('PostgreSQL pool initialized for bias metrics');
        } catch (pgError) {
          logger.warn({ error: pgError }, 'PostgreSQL pool initialization failed - bias metrics will be unavailable');
          dependencies.pgPool = undefined;
        }

        state.isReady = true;
        logger.info('hh-admin-svc fully initialized and ready');
      } catch (error) {
        logger.error({ error }, 'Failed to initialize dependencies - service running in degraded mode');
        // Service stays up but routes will fail when accessed
      }
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
