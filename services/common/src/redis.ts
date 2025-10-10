import Redis from 'ioredis';

import { getConfig } from './config';
import { getLogger } from './logger';

let client: Redis | null = null;
let connecting: Promise<Redis> | null = null;

export async function getRedisClient(): Promise<Redis> {
  if (client && client.status === 'ready') {
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

  // Build TLS options if enabled
  const tlsOptions = redisTls
    ? {
        rejectUnauthorized: process.env.REDIS_TLS_REJECT_UNAUTHORIZED !== 'false',
        ca: process.env.REDIS_TLS_CA ? [process.env.REDIS_TLS_CA] : undefined
      }
    : undefined;

  const redisClient = new Redis({
    host: config.redis.host,
    port: config.redis.port,
    password: config.redis.password,
    tls: tlsOptions,
    retryStrategy: (times: number) => {
      if (times > 10) {
        logger.error('Too many Redis reconnection attempts, giving up');
        return null;  // Stop retrying
      }
      // Exponential backoff: 100ms, 200ms, 400ms, 800ms, etc. (max 3s)
      const delay = Math.min(100 * Math.pow(2, times), 3000);
      logger.info({ retries: times, delay }, 'Reconnecting to Redis...');
      return delay;
    },
    // Enable TCP keepalive
    keepAlive: 5000
  });

  // Handle errors - clear cached client on fatal errors
  redisClient.on('error', (error: any) => {
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

  redisClient.on('connect', () => {
    logger.info('Connected to Redis.');
  });

  connecting = new Promise((resolve, reject) => {
    const readyHandler = () => {
      client = redisClient;
      connecting = null;
      logger.info('Redis connection established.');
      cleanup();
      resolve(redisClient);
    };

    const errorHandler = (error: Error) => {
      connecting = null;
      logger.error({ error }, 'Failed to connect to Redis.');
      cleanup();
      reject(error);
    };

    const cleanup = () => {
      redisClient.off('ready', readyHandler);
      redisClient.off('error', errorHandler);
    };

    redisClient.once('ready', readyHandler);
    redisClient.once('error', errorHandler);
  });

  return connecting;
}

export async function closeRedisClient(): Promise<void> {
  if (connecting) {
    await connecting.catch(() => undefined);
  }

  if (client && client.status === 'ready') {
    await client.quit();
  }

  client = null;
}

export function resetRedisForTesting(): void {
  client = null;
  connecting = null;
}
