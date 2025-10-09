import { createClient } from 'redis';

import { getConfig } from './config';
import { getLogger } from './logger';

let client: any | null = null;
let connecting: Promise<any> | null = null;

export async function getRedisClient(): Promise<any> {
  if (client && client.isReady) {
    return client;
  }

  if (connecting) {
    return connecting;
  }

  const config = getConfig();
  const logger = getLogger({ module: 'redis' });

  // Check for TLS configuration from environment variables
  const redisTls = process.env.REDIS_TLS === 'true';

  logger.info(
    {
      host: config.redis.host,
      port: config.redis.port,
      tls: redisTls
    },
    'Initializing Redis client...'
  );

  // Build socket configuration with optional TLS
  const socketConfig: any = {
    host: config.redis.host,
    port: config.redis.port
  };

  if (redisTls) {
    socketConfig.tls = {
      rejectUnauthorized: process.env.REDIS_TLS_REJECT_UNAUTHORIZED !== 'false',
      ca: process.env.REDIS_TLS_CA ? [process.env.REDIS_TLS_CA] : undefined
    };
  }

  const redisClient = createClient({
    socket: socketConfig,
    password: config.redis.password
  });

  redisClient.on('error', (error) => {
    logger.error({ error }, 'Redis client encountered an error.');
  });

  connecting = redisClient
    .connect()
    .then(() => {
      client = redisClient;
      connecting = null;
      logger.info('Connected to Redis.');
      return redisClient;
    })
    .catch((error) => {
      connecting = null;
      logger.error({ error }, 'Failed to connect to Redis.');
      throw error;
    });

  return connecting;
}

export async function closeRedisClient(): Promise<void> {
  if (connecting) {
    await connecting.catch(() => undefined);
  }

  if (client && client.isReady) {
    await client.quit();
  }

  client = null;
}

export function resetRedisForTesting(): void {
  client = null;
  connecting = null;
}
