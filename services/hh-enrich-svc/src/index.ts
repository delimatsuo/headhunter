import 'dotenv/config';

import { buildServer, getLogger } from '@hh/common';

import { getEnrichServiceConfig } from './config';
import { EnrichmentJobStore } from './job-store';
import { EnrichmentService } from './enrichment-service';
import { registerRoutes } from './routes';
import { EnrichmentWorker } from './worker';
import { MetricsExporter } from './metrics-exporter';

async function bootstrap(): Promise<void> {
  process.env.SERVICE_NAME = process.env.SERVICE_NAME ?? 'hh-enrich-svc';

  const logger = getLogger({ module: 'enrich-bootstrap' });

  try {
    logger.info('Starting hh-enrich-svc bootstrap...');
    const config = getEnrichServiceConfig();
    logger.info('Configuration loaded');

    const server = await buildServer({ disableDefaultHealthRoute: true });
    logger.info('Fastify server built');

    // Track initialization state with mutable dependency container
    const state = {
      isReady: false
    };
    const dependencies = {
      config,
      service: null as EnrichmentService | null,
      jobStore: null as EnrichmentJobStore | null,
      worker: null as EnrichmentWorker | null,
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
    logger.info({ port }, 'hh-enrich-svc listening (initializing dependencies...)');

    // Initialize real dependencies in background (after listen)
    setImmediate(async () => {
      try {
        logger.info('Initializing metrics exporter...');
        const metricsExporter = MetricsExporter.fromEnv(
          config.base.firestore.projectId,
          config.base.runtime.serviceName,
          getLogger({ module: 'metrics-exporter' })
        ) ?? undefined;
        logger.info('Metrics exporter initialized');

        logger.info('Initializing job store...');
        dependencies.jobStore = new EnrichmentJobStore(config);
        logger.info('Job store initialized');

        logger.info('Initializing enrichment service...');
        dependencies.service = new EnrichmentService(config, dependencies.jobStore, metricsExporter);
        logger.info('Enrichment service initialized');

        logger.info('Initializing enrichment worker...');
        dependencies.worker = new EnrichmentWorker(config, dependencies.jobStore, dependencies.service, metricsExporter);
        logger.info('Enrichment worker initialized');

        logger.info('Starting enrichment worker...');
        await dependencies.worker.start();
        logger.info('Enrichment worker started');

        state.isReady = true;
        logger.info('hh-enrich-svc fully initialized and ready');
      } catch (error) {
        logger.error({ error }, 'Failed to initialize dependencies - service running in degraded mode');
        // Service stays up but routes will fail when accessed
      }
    });

    const shutdown = async () => {
      logger.info('Received shutdown signal.');
      try {
        if (dependencies.worker) {
          await dependencies.worker.stop();
        }
        await server.close();
        logger.info('hh-enrich-svc closed gracefully.');
        process.exit(0);
      } catch (error) {
        logger.error({ error }, 'Failed to shutdown gracefully.');
        process.exit(1);
      }
    };

    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);
  } catch (error) {
    logger.error({ error }, 'Failed to bootstrap hh-enrich-svc.');
    process.exit(1);
  }
}

void bootstrap();
