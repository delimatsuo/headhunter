import type { PerformanceSnapshot } from './performance-tracker';

interface MetricsClientOptions {
  baseUrl: string;
  fetchFn?: typeof fetch;
  timeoutMs?: number;
  apiKey?: string;
}

interface HealthResponse {
  status: string;
  metrics?: PerformanceSnapshot;
}

export class MetricsClient {
  private readonly baseUrl: string;
  private readonly fetchFn: typeof fetch;
  private readonly timeoutMs: number;
  private readonly apiKey?: string;

  constructor(options: MetricsClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, '');
    this.fetchFn = options.fetchFn ?? fetch;
    this.timeoutMs = Math.max(1000, options.timeoutMs ?? 5000);
    this.apiKey = options.apiKey ?? process.env.SEARCH_API_KEY;
  }

  async fetchSnapshot(): Promise<PerformanceSnapshot> {
    const controller = new AbortController();
    const timeout = setTimeout(() => {
      controller.abort();
    }, this.timeoutMs);

    try {
      const url = new URL(`${this.baseUrl}/health`);
      if (this.apiKey) {
        url.searchParams.set('key', this.apiKey);
      }

      const response = await this.fetchFn(url, {
        method: 'GET',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json'
        }
      });

      const payload = (await response.json()) as HealthResponse;
      if (!payload.metrics) {
        throw new Error('Performance metrics payload missing in readiness response.');
      }
      return payload.metrics;
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error(`Request to ${this.baseUrl}/health timed out after ${this.timeoutMs}ms`);
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }
}
