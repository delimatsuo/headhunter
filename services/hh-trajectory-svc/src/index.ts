import { buildServer, getLogger } from '@hh/common';

import { getTrajectoryServiceConfig } from './config';
import { healthRoutes } from './routes/health';
import { predictRoutes } from './routes/predict';
import { shadowStatsRoutes } from './routes/shadow-stats';
import { TrajectoryPredictor, ONNXSession } from './inference';
import ShadowMode from './shadow/shadow-mode.js';

async function bootstrap(): Promise<void> {
  process.env.SERVICE_NAME = process.env.SERVICE_NAME ?? 'hh-trajectory-svc';
  const logger = getLogger({ module: 'bootstrap' });

  try {
    logger.info('Starting hh-trajectory-svc bootstrap...');

    const config = getTrajectoryServiceConfig();
    logger.info({ serviceName: config.base.runtime.serviceName }, 'Configuration loaded');

    const server = await buildServer({
      disableDefaultHealthRoute: true,
      disableRateLimit: true, // Disable until rate-limit plugin version is fixed
      disableAuth: true, // TODO: Enable auth after integration testing
      disableTenantValidation: true // TODO: Enable after auth is enabled
    });
    logger.info('Fastify server built');

    // Initialize shadow mode for ML vs rule-based comparison logging
    const shadowMode = new ShadowMode({
      enabled: process.env.SHADOW_MODE_ENABLED === 'true', // Default: false
      loggerConfig: {
        batchSize: 100,
        flushIntervalMs: 60_000, // Flush every 60 seconds
        storageType: 'memory' // Use in-memory storage for now (TODO: postgres/bigquery)
      }
    });
    logger.info({ shadowModeEnabled: shadowMode.isEnabled() }, 'Shadow mode initialized');

    // Track initialization state with mutable dependency container
    const predictor = new TrajectoryPredictor(config);
    const state = {
      isReady: false,
      modelLoaded: false,
      predictor,
      shadowMode
    };

    // Register ALL routes BEFORE listen (required by Fastify)
    // Routes will use lazily-initialized dependencies via closure
    logger.info('Registering routes (with lazy dependencies)...');
    await healthRoutes(server, state);
    await predictRoutes(server, state);
    await shadowStatsRoutes(server, shadowMode);
    logger.info('Routes registered');

    // Register under-pressure plugin BEFORE listen (required by Fastify)
    logger.info('Registering under-pressure plugin...');
    const underPressure = await import('@fastify/under-pressure');
    await server.register(underPressure.default, {
      maxEventLoopDelay: 2000,
      maxHeapUsedBytes: 1_024 * 1_024 * 1024,
      maxRssBytes: 1_536 * 1_024 * 1024,
      healthCheck: async () => {
        // Return true if model is loaded, otherwise service is healthy but degraded
        if (!state.modelLoaded) {
          throw new Error('Model not loaded yet');
        }
        return true;
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
        logger.info({ modelPath: config.modelPath }, 'Initializing trajectory predictor...');

        await predictor.initialize();

        state.modelLoaded = true;
        state.isReady = true;

        logger.info('hh-trajectory-svc fully initialized and ready');
      } catch (error) {
        const errorDetails = error instanceof Error
          ? { name: error.name, message: error.message, stack: error.stack }
          : { raw: String(error) };
        logger.error({ error: errorDetails }, 'Failed to initialize trajectory predictor - service running in degraded mode');
        // Service stays up but routes will return errors when accessed
      }
    });

    const shutdown = async () => {
      logger.info('Received shutdown signal.');
      try {
        // Dispose shadow mode (flush remaining logs)
        await shadowMode.dispose();
        logger.info('Shadow mode disposed');

        // Dispose ONNX session
        await ONNXSession.dispose();

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
