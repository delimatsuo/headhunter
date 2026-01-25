import { buildServer, getLogger } from '@hh/common';

import { getTrajectoryServiceConfig } from './config';
import { healthRoutes } from './routes/health';
import { predictRoutes } from './routes/predict';

async function bootstrap(): Promise<void> {
  process.env.SERVICE_NAME = process.env.SERVICE_NAME ?? 'hh-trajectory-svc';
  const logger = getLogger({ module: 'bootstrap' });

  try {
    logger.info('Starting hh-trajectory-svc bootstrap...');

    const config = getTrajectoryServiceConfig();
    logger.info({ serviceName: config.base.runtime.serviceName }, 'Configuration loaded');

    const server = await buildServer({ disableDefaultHealthRoute: true });
    logger.info('Fastify server built');

    // Track initialization state with mutable dependency container
    const state = {
      isReady: false,
      modelLoaded: false
    };

    // Register ALL routes BEFORE listen (required by Fastify)
    // Routes will use lazily-initialized dependencies via closure
    logger.info('Registering routes (with lazy dependencies)...');
    await healthRoutes(server, state);
    await predictRoutes(server, state);
    logger.info('Routes registered');

    // Register under-pressure plugin BEFORE listen (required by Fastify)
    logger.info('Registering under-pressure plugin...');
    const underPressure = await import('@fastify/under-pressure');
    await server.register(underPressure.default, {
      maxEventLoopDelay: 2000,
      maxHeapUsedBytes: 1_024 * 1_024 * 1024,
      maxRssBytes: 1_536 * 1_024 * 1024,
      healthCheck: async () => {
        // Basic health check - model loading happens in background
        return state.modelLoaded;
      },
      healthCheckInterval: 10000
    });
    logger.info('Under-pressure plugin registered');

    // Start listening IMMEDIATELY (Cloud Run requires fast startup)
    const port = config.port;
    const host = '0.0.0.0';
    await server.listen({ port, host });
    logger.info({ port, service: config.base.runtime.serviceName }, 'hh-trajectory-svc listening (initializing model...)');

    // Initialize ONNX model in background (after listen)
    setImmediate(async () => {
      try {
        logger.info({ modelPath: config.modelPath }, 'Initializing ONNX model...');

        // Model loading will be implemented in Plan 02
        // For now, just mark as ready
        state.modelLoaded = true;
        state.isReady = true;

        logger.info('hh-trajectory-svc fully initialized and ready');
      } catch (error) {
        const errorDetails = error instanceof Error
          ? { name: error.name, message: error.message, stack: error.stack }
          : { raw: String(error) };
        logger.error({ error: errorDetails }, 'Failed to initialize ONNX model - service running in degraded mode');
        // Service stays up but routes will return errors when accessed
      }
    });

    const shutdown = async () => {
      logger.info('Received shutdown signal.');
      try {
        await server.close();
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
    logger.error({ error }, 'Failed to bootstrap hh-trajectory-svc');
    process.exit(1);
  }
}

void bootstrap();
