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
  const config = getAdminServiceConfig();
  const pubsubClient = new AdminPubSubClient(config.pubsub);
  const jobsClient = new AdminJobsClient(config.jobs, config.scheduler);
  const monitoringClient = new MonitoringClient(config.monitoring);
  const iamValidator = new AdminIamValidator(config.iam);
  const service = new AdminService(config, pubsubClient, jobsClient, monitoringClient);

  const server = await buildServer({ disableDefaultHealthRoute: true });
  await registerRoutes(server, {
    config,
    service,
    pubsub: pubsubClient,
    jobs: jobsClient,
    monitoring: monitoringClient,
    iam: iamValidator
  });

  const port = Number(process.env.PORT ?? 8080);
  const host = '0.0.0.0';

  await server.listen({ port, host });
  logger.info({ port }, 'hh-admin-svc listening.');

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
}

void bootstrap();
