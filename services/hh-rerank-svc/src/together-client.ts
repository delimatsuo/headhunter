import axios, { AxiosError } from 'axios';
import type { AxiosInstance } from 'axios';
import type { Logger } from 'pino';

import type { TogetherAIConfig } from './config.js';
import type {
  TogetherChatCompletionRequestPayload,
  TogetherChatCompletionResponsePayload
} from './types.js';

type PRetryExports = {
  default: typeof import('p-retry')['default'];
  AbortError: typeof import('p-retry')['AbortError'];
};

type PTimeoutExports = {
  default: typeof import('p-timeout')['default'];
};

let pRetryModule: PRetryExports | null = null;
let pTimeoutModule: PTimeoutExports | null = null;

async function loadModule<T>(loader: () => Promise<T>, moduleName: string): Promise<T> {
  try {
    return await loader();
  } catch (error) {
    const loadError = new Error(`Failed to load ${moduleName} via dynamic import.`);
    (loadError as Error & { cause?: unknown }).cause = error;
    throw loadError;
  }
}

async function getPRetry(): Promise<PRetryExports> {
  if (!pRetryModule) {
    const module = (await loadModule(() => import('p-retry'), 'p-retry')) as unknown;
    const moduleAny = module as Record<string, unknown> & {
      default?: PRetryExports['default'];
      AbortError?: PRetryExports['AbortError'];
    };
    const resolvedDefault = (moduleAny?.default ?? moduleAny) as PRetryExports['default'];

    if (typeof resolvedDefault !== 'function') {
      throw new Error('p-retry default export did not resolve to a function.');
    }

    const resolvedAbort = (moduleAny?.AbortError ?? (resolvedDefault as unknown as { AbortError?: unknown })?.AbortError ?? Error) as PRetryExports['AbortError'];

    pRetryModule = {
      default: resolvedDefault,
      AbortError: resolvedAbort
    } satisfies PRetryExports;
  }

  return pRetryModule;
}

async function getPTimeout(): Promise<PTimeoutExports> {
  if (!pTimeoutModule) {
    const module = (await loadModule(() => import('p-timeout'), 'p-timeout')) as unknown;
    const moduleAny = module as Record<string, unknown> & {
      default?: PTimeoutExports['default'];
    };
    const resolvedDefault = (moduleAny?.default ?? moduleAny) as PTimeoutExports['default'];

    if (typeof resolvedDefault !== 'function') {
      throw new Error('p-timeout default export did not resolve to a function.');
    }

    pTimeoutModule = {
      default: resolvedDefault
    } satisfies PTimeoutExports;
  }

  return pTimeoutModule;
}

export interface TogetherHealthStatus {
  status: 'healthy' | 'degraded' | 'disabled' | 'unavailable';
  circuitOpen?: boolean;
  failureCount?: number;
  message?: string;
  lastFailureAt?: string;
}

export interface TogetherRerankOptions {
  requestId: string;
  tenantId: string;
  topN: number;
  context?: Record<string, unknown>;
  budgetMs?: number;
}

export class TogetherClient {
  private readonly axios: AxiosInstance | null;
  private failureCount = 0;
  private circuitOpenedAt: number | null = null;

  constructor(private readonly config: TogetherAIConfig, private readonly logger: Logger) {
    if (!config.enable) {
      this.logger.warn('Together AI integration disabled. Falling back to passthrough ranking.');
      this.axios = null;
      return;
    }

    this.axios = axios.create({
      baseURL: config.baseUrl,
      timeout: config.timeoutMs,
      headers: {
        Authorization: `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json'
      }
    });
  }

  private isCircuitOpen(): boolean {
    if (!this.circuitOpenedAt) {
      return false;
    }

    const elapsed = Date.now() - this.circuitOpenedAt;
    if (elapsed > this.config.circuitBreakerCooldownMs) {
      this.logger.warn({ elapsed }, 'Together circuit breaker cooldown elapsed. Closing circuit.');
      this.circuitOpenedAt = null;
      this.failureCount = 0;
      return false;
    }

    return true;
  }

  private recordFailure(error: unknown): void {
    this.failureCount += 1;
    if (this.failureCount >= this.config.circuitBreakerThreshold) {
      if (!this.circuitOpenedAt) {
        this.circuitOpenedAt = Date.now();
        this.logger.error({ error, failureCount: this.failureCount }, 'Together circuit breaker opened.');
      }
    }
  }

  private recordSuccess(): void {
    this.failureCount = 0;
    this.circuitOpenedAt = null;
  }

  async rerank(
    payload: TogetherChatCompletionRequestPayload,
    options: TogetherRerankOptions
  ): Promise<{ data: TogetherChatCompletionResponsePayload; latencyMs: number } | null> {
    if (!this.config.enable || !this.axios) {
      this.logger.debug('Together rerank skipped because client is disabled.');
      return null;
    }

    if (this.isCircuitOpen()) {
      this.logger.warn({ tenantId: options.tenantId }, 'Together circuit open. Skipping rerank.');
      return null;
    }

    const startedAt = Date.now();
    const deadline = typeof options.budgetMs === 'number' ? startedAt + options.budgetMs : null;
    const retries =
      typeof options.budgetMs === 'number' && options.budgetMs < this.config.timeoutMs
        ? 0
        : this.config.retries;

    const retryModule = await getPRetry();
    const timeoutModule = await getPTimeout();
    const pRetry = retryModule.default;
    const AbortError = retryModule.AbortError as unknown as typeof import('p-retry')['AbortError'];
    const pTimeout = timeoutModule.default;

    try {
      const data = await pRetry(
        async (attempt) => {
          try {
            const now = Date.now();
            const remainingBudget = deadline ? deadline - now : undefined;

            if (typeof remainingBudget === 'number' && remainingBudget <= 50) {
              this.logger.warn({ remainingBudget, attempt }, 'Together chat completion budget exhausted.');
              throw new AbortError(new Error('Together chat completion budget exhausted.'));
            }

            const axiosTimeout = Math.max(
              100,
              Math.min(
                this.config.timeoutMs,
                typeof remainingBudget === 'number' ? remainingBudget : this.config.timeoutMs
              )
            );

            const hardTimeout =
              typeof remainingBudget === 'number'
                ? Math.max(100, Math.min(axiosTimeout + 50, remainingBudget))
                : axiosTimeout + 50;

            const response = await pTimeout(
              this.axios!.post<TogetherChatCompletionResponsePayload>('/chat/completions', payload, {
                headers: {
                  'x-request-id': options.requestId,
                  'x-tenant-id': options.tenantId
                },
                timeout: axiosTimeout
              }),
              {
                milliseconds: hardTimeout,
                message: 'Together chat completion timed out.'
              }
            );

            this.recordSuccess();
            return response.data;
          } catch (error) {
            const isTimeout = this.isTimeoutError(error);
            const axiosError = error as AxiosError;
            const status = axiosError?.response?.status;
            const retryable = !isTimeout && status !== undefined && status >= 500;

            if (isTimeout) {
              this.logger.warn({ attempt }, 'Together chat completion timed out.');
              throw new AbortError(error as Error);
            }

            if (!retryable) {
              throw new AbortError(error as Error);
            }

            this.logger.warn({ attempt, error: axiosError?.message ?? String(error) }, 'Together chat completion attempt failed.');
            throw error;
          }
        },
        {
          retries,
          factor: 1,
          minTimeout: this.config.retryDelayMs,
          maxTimeout: this.config.retryDelayMs * 3,
          onFailedAttempt: (error) => {
            this.recordFailure(error);
          }
        }
      );

      const latencyMs = Date.now() - startedAt;

      if (latencyMs > this.config.timeoutMs) {
        this.logger.warn({ latencyMs, target: this.config.timeoutMs }, 'Together chat completion exceeded timeout budget.');
      }

      return { data, latencyMs };
    } catch (error) {
      const originalError = (error as { originalError?: unknown }).originalError ?? error;

      if (originalError instanceof Error && originalError.message.includes('budget exhausted')) {
        this.logger.warn({ tenantId: options.tenantId }, 'Together chat completion skipped due to exhausted budget.');
        return null;
      }

      this.recordFailure(originalError);

      if (this.isTimeoutError(originalError)) {
        this.logger.warn({ tenantId: options.tenantId }, 'Together chat completion timed out. Falling back.');
        return null;
      }

      if (axios.isAxiosError?.(originalError)) {
        const axiosError = originalError as AxiosError;
        this.logger.error(
          {
            status: axiosError.response?.status,
            data: axiosError.response?.data,
            message: axiosError.message
          },
          'Together chat completion failed with Axios error.'
        );
      } else {
        this.logger.error({ error: originalError }, 'Together chat completion failed.');
      }

      return null;
    }
  }

  private isTimeoutError(error: unknown): boolean {
    if (!error) {
      return false;
    }

    if (error instanceof Error && error.name === 'TimeoutError') {
      return true;
    }

    if (error instanceof Error && error.message.toLowerCase().includes('timed out')) {
      return true;
    }

    const axiosError = error as AxiosError;
    if (axiosError?.code && ['ECONNABORTED', 'ETIMEDOUT', 'ECONNRESET'].includes(axiosError.code)) {
      return true;
    }
    if (axiosError?.response?.status === 504) {
      return true;
    }

    return false;
  }

  async healthCheck(): Promise<TogetherHealthStatus> {
    if (!this.config.enable) {
      return { status: 'disabled', message: 'Together AI disabled via configuration.' } satisfies TogetherHealthStatus;
    }

    if (!this.axios) {
      return { status: 'unavailable', message: 'Together client not initialised.' } satisfies TogetherHealthStatus;
    }

    if (this.isCircuitOpen()) {
      return {
        status: 'degraded',
        circuitOpen: true,
        failureCount: this.failureCount,
        lastFailureAt: new Date(this.circuitOpenedAt ?? Date.now()).toISOString()
      } satisfies TogetherHealthStatus;
    }

    return { status: 'healthy', failureCount: this.failureCount } satisfies TogetherHealthStatus;
  }

  async close(): Promise<void> {
    // Nothing to close explicitly but method kept for parity with other services.
  }
}
