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

  const redisClient = createClient({
    socket: {
      host: config.redis.host,
      port: config.redis.port
    },
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
