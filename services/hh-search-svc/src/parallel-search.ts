import type { Logger } from 'pino';

export interface ParallelTimings {
  embeddingMs?: number;
  specialtyMs?: number;
  vectorSearchMs?: number;
  textSearchMs?: number;
  parallelSavingsMs: number;
}

export interface EmbeddingResult {
  embedding: number[];
  fromCache: boolean;
}

export interface SpecialtyResult {
  specialtyMatch: string | null;
  fromCache: boolean;
}

/**
 * Execute embedding generation and specialty lookup in parallel.
 * Both operations are independent and can run concurrently.
 *
 * Uses Promise.allSettled to handle partial failures gracefully.
 * If one operation fails, the other can still succeed.
 *
 * @param embeddingFetcher - Async function to fetch or generate embedding
 * @param specialtyFetcher - Async function to fetch specialty data
 * @param logger - Logger instance for tracking failures
 * @returns Object containing both results and timing metrics
 */
export async function executeParallelPreSearch<E, S>(
  embeddingFetcher: () => Promise<E>,
  specialtyFetcher: () => Promise<S>,
  logger: Logger
): Promise<{
  embedding: E | null;
  specialty: S | null;
  timings: { embeddingMs: number; specialtyMs: number; totalMs: number };
}> {
  const start = Date.now();

  const results = await Promise.allSettled([
    embeddingFetcher(),
    specialtyFetcher()
  ]);

  const embeddingResult = results[0];
  const specialtyResult = results[1];

  const embedding = embeddingResult.status === 'fulfilled' ? embeddingResult.value : null;
  const specialty = specialtyResult.status === 'fulfilled' ? specialtyResult.value : null;

  // Log any failures for debugging
  if (embeddingResult.status === 'rejected') {
    logger.warn({ error: embeddingResult.reason }, 'Parallel embedding fetch failed');
  }
  if (specialtyResult.status === 'rejected') {
    logger.warn({ error: specialtyResult.reason }, 'Parallel specialty fetch failed');
  }

  const totalMs = Date.now() - start;

  // For parallel operations, both complete at the same time (totalMs)
  // Individual times would only be meaningful if we tracked them separately
  const embeddingMs = embeddingResult.status === 'fulfilled' ? totalMs : 0;
  const specialtyMs = specialtyResult.status === 'fulfilled' ? totalMs : 0;

  return {
    embedding,
    specialty,
    timings: {
      embeddingMs,
      specialtyMs,
      totalMs
    }
  };
}

/**
 * Request coalescing to prevent duplicate concurrent requests.
 * If a request with the same key is already in-flight, return the existing promise.
 *
 * This is crucial for embedding generation - if multiple concurrent search requests
 * need the same embedding, they should share a single generation request.
 */
export class RequestCoalescer<T> {
  private pendingRequests = new Map<string, Promise<T>>();

  async getOrFetch(key: string, fetcher: () => Promise<T>): Promise<T> {
    // Check if request already in-flight
    const existing = this.pendingRequests.get(key);
    if (existing) {
      return existing;
    }

    // Create new request and track it
    const promise = fetcher().finally(() => {
      this.pendingRequests.delete(key);
    });

    this.pendingRequests.set(key, promise);
    return promise;
  }

  clear(): void {
    this.pendingRequests.clear();
  }

  /**
   * Get count of pending requests for metrics/debugging
   */
  get pendingCount(): number {
    return this.pendingRequests.size;
  }
}

/**
 * Calculate parallel execution savings compared to sequential.
 *
 * Sequential execution: operation1Ms + operation2Ms
 * Parallel execution: max(operation1Ms, operation2Ms)
 * Savings: sequentialMs - parallelMs
 *
 * @param parallelMs - Actual time taken when running in parallel
 * @param operation1Ms - Time first operation would take alone
 * @param operation2Ms - Time second operation would take alone
 * @returns Time saved by running in parallel (always >= 0)
 */
export function calculateParallelSavings(
  parallelMs: number,
  operation1Ms: number,
  operation2Ms: number
): number {
  const sequentialMs = operation1Ms + operation2Ms;
  return Math.max(0, sequentialMs - parallelMs);
}
