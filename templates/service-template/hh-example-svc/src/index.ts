import { buildServer, getConfig, getLogger } from '@hh/common';

import { registerRoutes } from './routes';

async function main(): Promise<void> {
  const config = getConfig();
  const logger = getLogger({ module: 'bootstrap' });

  try {
    const server = await buildServer({ disableDefaultHealthRoute: true });
    await registerRoutes(server);

    const port = Number(process.env.PORT ?? 8080);
    const host = '0.0.0.0';

    await server.listen({ port, host });
    logger.info({ port, service: config.runtime.serviceName }, 'Service started.');

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
    logger.error({ error }, 'Failed to start service.');
    process.exit(1);
  }
}

void main();
