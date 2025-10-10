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
    port: config.redis.port,
    // Critical: Enable TCP keepalive to prevent connection resets
    keepAlive: 5000, // Send keepalive probes every 5 seconds
    // Reconnection strategy
    reconnectStrategy: (retries: number) => {
      if (retries > 10) {
        logger.error('Too many Redis reconnection attempts, giving up');
        return new Error('Too many reconnection attempts');
      }
      // Exponential backoff: 100ms, 200ms, 400ms, 800ms, etc. (max 3s)
      const delay = Math.min(100 * Math.pow(2, retries), 3000);
      logger.info({ retries, delay }, 'Reconnecting to Redis...');
      return delay;
    }
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

  // Handle errors - clear cached client on fatal errors
  redisClient.on('error', (error) => {
    logger.error({ error }, 'Redis client encountered an error.');
    // On connection errors, clear the cached client so next call creates a new one
    if (error.code === 'ECONNRESET' || error.code === 'ECONNREFUSED') {
      logger.warn('Clearing cached Redis client due to connection error');
      client = null;
    }
  });

  // Handle reconnection events
  redisClient.on('reconnecting', () => {
    logger.info('Redis client reconnecting...');
  });

  redisClient.on('ready', () => {
    logger.info('Redis client ready');
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
