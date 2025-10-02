import type { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import fp from 'fastify-plugin';

import { getFirestore } from './firestore';
import { getLogger } from './logger';
import type { ErrorResponse, RequestContext } from './types';

export interface ServiceErrorOptions {
  statusCode?: number;
  code?: string;
  details?: Record<string, unknown>;
  cause?: Error;
}

export class ServiceError extends Error {
  public readonly statusCode: number;
  public readonly code: string;
  public readonly details?: Record<string, unknown>;

  constructor(message: string, { statusCode = 500, code = 'internal', details, cause }: ServiceErrorOptions = {}) {
    super(message);
    this.name = 'ServiceError';
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
    if (cause) {
      this.cause = cause;
    }
  }
}

type ErrorFactory = (message: string, details?: Record<string, unknown>) => ServiceError;

function errorFactory(statusCode: number, code: string): ErrorFactory {
  return (message: string, details?: Record<string, unknown>) => new ServiceError(message, { statusCode, code, details });
}

export const badRequestError = errorFactory(400, 'bad_request');
export const unauthorizedError = errorFactory(401, 'unauthorized');
export const forbiddenError = errorFactory(403, 'forbidden');
export const notFoundError = errorFactory(404, 'not_found');
export const conflictError = errorFactory(409, 'conflict');
export const tooManyRequestsError = errorFactory(429, 'rate_limited');
export const internalError = errorFactory(500, 'internal');

interface SanitizedError {
  statusCode: number;
  payload: ErrorResponse;
}

function sanitizeError(err: unknown): SanitizedError {
  if (err instanceof ServiceError) {
    return {
      statusCode: err.statusCode,
      payload: {
        code: err.code,
        message: err.message,
        details: err.details
      }
    };
  }

  if (err instanceof Error) {
    return {
      statusCode: 500,
      payload: {
        code: 'internal',
        message: 'An unexpected error occurred.'
      }
    };
  }

  return {
    statusCode: 500,
    payload: {
      code: 'internal',
      message: 'Unknown error.'
    }
  };
}

async function persistError(request: FastifyRequest, error: ErrorResponse, statusCode: number): Promise<void> {
  const firestore = getFirestore();

  try {
    await firestore.collection('service_errors').add({
      createdAt: new Date().toISOString(),
      requestId: request.requestContext?.requestId,
      path: request.url,
      method: request.method,
      statusCode,
      error,
      tenantId: request.tenant?.id ?? null,
      userId: request.user?.uid ?? null
    });
  } catch (firestoreError) {
    const logger = getLogger({ module: 'error-logger' });
    logger.warn({ firestoreError }, 'Failed to persist error to Firestore.');
  }
}

function shouldLogError(statusCode: number): boolean {
  return statusCode >= 500;
}

export const errorHandlerPlugin: FastifyPluginAsync = fp(async (fastify) => {
  const logger = getLogger({ module: 'error-handler' });

  fastify.setErrorHandler(async (err: unknown, request: FastifyRequest, reply: FastifyReply) => {
    const sanitized = sanitizeError(err);
    const requestContext = request.requestContext as RequestContext | undefined;

    if (shouldLogError(sanitized.statusCode)) {
      logger.error({ err, requestId: requestContext?.requestId }, 'Request failed with server error.');
    } else {
      logger.warn({ err, requestId: requestContext?.requestId }, 'Request failed with client error.');
    }

    if (sanitized.statusCode >= 500) {
      void persistError(request, sanitized.payload, sanitized.statusCode);
    }

    if (!reply.sent) {
      reply.status(sanitized.statusCode).send(sanitized.payload);
    }
  });
});

export interface CircuitBreakerOptions {
  failureThreshold: number;
  successThreshold: number;
  timeoutMs: number;
}

export type CircuitBreakerState = 'CLOSED' | 'OPEN' | 'HALF_OPEN';

export class CircuitBreaker {
  private state: CircuitBreakerState = 'CLOSED';
  private failureCount = 0;
  private successCount = 0;
  private nextAttempt = Date.now();

  constructor(private readonly options: CircuitBreakerOptions) {}

  public async exec<T>(action: () => Promise<T>): Promise<T> {
    if (this.state === 'OPEN') {
      if (Date.now() >= this.nextAttempt) {
        this.state = 'HALF_OPEN';
      } else {
        throw tooManyRequestsError('Circuit breaker is open.');
      }
    }

    try {
      const result = await action();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private onSuccess(): void {
    if (this.state === 'HALF_OPEN') {
      this.successCount += 1;
      if (this.successCount >= this.options.successThreshold) {
        this.reset();
      }
    } else {
      this.reset();
    }
  }

  private onFailure(): void {
    this.failureCount += 1;

    if (this.failureCount >= this.options.failureThreshold) {
      this.trip();
    }
  }

  private reset(): void {
    this.failureCount = 0;
    this.successCount = 0;
    this.state = 'CLOSED';
  }

  private trip(): void {
    this.state = 'OPEN';
    this.nextAttempt = Date.now() + this.options.timeoutMs;
  }
}

export interface RetryOptions {
  retries: number;
  factor?: number;
  minTimeoutMs?: number;
}

export async function withRetry<T>(fn: () => Promise<T>, { retries, factor = 2, minTimeoutMs = 200 }: RetryOptions): Promise<T> {
  let attempt = 0;
  let lastError: unknown;

  while (attempt <= retries) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt === retries) {
        break;
      }

      const wait = minTimeoutMs * Math.pow(factor, attempt);
      await new Promise((resolve) => setTimeout(resolve, wait));
      attempt += 1;
    }
  }

  throw lastError;
}

export function respondWithError(reply: FastifyReply, err: ServiceError): void {
  const payload: ErrorResponse = {
    code: err.code,
    message: err.message,
    details: err.details
  };

  reply.status(err.statusCode).send(payload);
}
