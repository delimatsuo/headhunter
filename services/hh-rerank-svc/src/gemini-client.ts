import type { Logger } from 'pino';
import { VertexAI, type GenerateContentRequest, type GenerativeModel, SchemaType } from '@google-cloud/vertexai';

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

export interface GeminiConfig {
  projectId: string;
  location: string;
  model: string;
  timeoutMs: number;
  retries: number;
  retryDelayMs: number;
  circuitBreakerThreshold: number;
  circuitBreakerCooldownMs: number;
  enable: boolean;
}

export interface GeminiHealthStatus {
  status: 'healthy' | 'degraded' | 'disabled' | 'unavailable';
  circuitOpen?: boolean;
  failureCount?: number;
  message?: string;
  lastFailureAt?: string;
}

export interface GeminiRerankOptions {
  requestId: string;
  tenantId: string;
  topN: number;
  context?: Record<string, unknown>;
  budgetMs?: number;
}

export interface GeminiRerankRequest {
  jobDescription: string;
  candidates: Array<{
    candidateId: string;
    summary?: string;
    highlights?: string[];
    skills?: string[];
  }>;
  topN: number;
  includeReasons: boolean;
}

export interface GeminiRerankResponse {
  candidates: Array<{
    candidateId: string;
    rank: number;
    score: number;
    reasons: string[];
  }>;
}

export class GeminiClient {
  private readonly vertexAI: VertexAI | null;
  private readonly model: GenerativeModel | null;
  private failureCount = 0;
  private circuitOpenedAt: number | null = null;

  constructor(private readonly config: GeminiConfig, private readonly logger: Logger) {
    if (!config.enable) {
      this.logger.warn('Gemini integration disabled. Falling back to passthrough ranking.');
      this.vertexAI = null;
      this.model = null;
      return;
    }

    try {
      this.vertexAI = new VertexAI({
        project: config.projectId,
        location: config.location
      });

      this.model = this.vertexAI.getGenerativeModel({
        model: config.model,
        generationConfig: {
          responseMimeType: 'application/json',
          responseSchema: {
            type: SchemaType.OBJECT,
            properties: {
              candidates: {
                type: SchemaType.ARRAY,
                items: {
                  type: SchemaType.OBJECT,
                  properties: {
                    candidateId: { type: SchemaType.STRING },
                    rank: { type: SchemaType.INTEGER },
                    score: { type: SchemaType.NUMBER },
                    reasons: {
                      type: SchemaType.ARRAY,
                      items: { type: SchemaType.STRING }
                    }
                  },
                  required: ['candidateId', 'rank', 'score', 'reasons']
                }
              }
            },
            required: ['candidates']
          },
          // @ts-expect-error - thinking_config is a new feature not yet in the types
          thinking_config: {
            thinking_budget: 0
          }
        }
      });

      this.logger.info({ model: config.model, project: config.projectId }, 'Gemini client initialized.');
    } catch (error) {
      this.logger.error({ error }, 'Failed to initialize Gemini client.');
      this.vertexAI = null;
      this.model = null;
    }
  }

  private isCircuitOpen(): boolean {
    if (!this.circuitOpenedAt) {
      return false;
    }

    const elapsed = Date.now() - this.circuitOpenedAt;
    if (elapsed > this.config.circuitBreakerCooldownMs) {
      this.logger.warn({ elapsed }, 'Gemini circuit breaker cooldown elapsed. Closing circuit.');
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
        this.logger.error({ error, failureCount: this.failureCount }, 'Gemini circuit breaker opened.');
      }
    }
  }

  private recordSuccess(): void {
    this.failureCount = 0;
    this.circuitOpenedAt = null;
  }

  private buildPrompt(request: GeminiRerankRequest): string {
    const candidatesText = request.candidates
      .map((c, idx) => {
        const parts: string[] = [`Candidate ${idx + 1} (ID: ${c.candidateId}):`];
        if (c.summary) {
          parts.push(`Summary: ${c.summary}`);
        }
        if (c.highlights && c.highlights.length > 0) {
          parts.push(`Highlights: ${c.highlights.join(', ')}`);
        }
        if (c.skills && c.skills.length > 0) {
          parts.push(`Skills: ${c.skills.join(', ')}`);
        }
        return parts.join('\n');
      })
      .join('\n\n');

    const reasonsInstruction = request.includeReasons
      ? 'For each candidate, provide 2-3 specific reasons explaining why they are a good fit for this role.'
      : 'Provide reasons as empty arrays.';

    return `You are an expert recruiter analyzing candidates for a job opening.

Job Description:
${request.jobDescription}

Candidates to Rank:
${candidatesText}

Task:
1. Analyze each candidate's qualifications against the job requirements
2. Rank them from best to worst fit (rank 1 = best match)
3. Assign each a relevance score from 0.0 to 1.0 (1.0 = perfect match)
4. ${reasonsInstruction}

CRITICAL: You MUST include ALL candidate IDs in your response. Return exactly ${request.candidates.length} candidates.
CRITICAL: Use the EXACT candidateId values provided above. Do not modify or generate new IDs.

Return your analysis in JSON format matching this exact structure:
{
  "candidates": [
    {
      "candidateId": "exact-id-from-input",
      "rank": 1,
      "score": 0.95,
      "reasons": ["reason 1", "reason 2"]
    }
  ]
}`;
  }

  async rerank(
    request: GeminiRerankRequest,
    options: GeminiRerankOptions
  ): Promise<{ data: GeminiRerankResponse; latencyMs: number } | null> {
    if (!this.config.enable || !this.model) {
      this.logger.debug('Gemini rerank skipped because client is disabled.');
      return null;
    }

    if (this.isCircuitOpen()) {
      this.logger.warn({ tenantId: options.tenantId }, 'Gemini circuit open. Skipping rerank.');
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
      const prompt = this.buildPrompt(request);

      const data = await pRetry(
        async (attempt) => {
          try {
            const now = Date.now();
            const remainingBudget = deadline ? deadline - now : undefined;

            if (typeof remainingBudget === 'number' && remainingBudget <= 50) {
              this.logger.warn({ remainingBudget, attempt }, 'Gemini budget exhausted.');
              throw new AbortError(new Error('Gemini budget exhausted.'));
            }

            const effectiveTimeout = Math.max(
              100,
              Math.min(
                this.config.timeoutMs,
                typeof remainingBudget === 'number' ? remainingBudget : this.config.timeoutMs
              )
            );

            const hardTimeout =
              typeof remainingBudget === 'number'
                ? Math.max(100, Math.min(effectiveTimeout + 50, remainingBudget))
                : effectiveTimeout + 50;

            const generateRequest: GenerateContentRequest = {
              contents: [{ role: 'user', parts: [{ text: prompt }] }],
              generationConfig: {
                // @ts-expect-error - thinking_config is a new feature
                thinking_config: {
                  thinking_budget: 0
                }
              }
            };

            const result = await pTimeout(
              this.model!.generateContent(generateRequest),
              {
                milliseconds: hardTimeout,
                message: 'Gemini generateContent timed out.'
              }
            ) as { response: { candidates: Array<{ content: { parts: Array<{ text: string }> } }> } };

            if (!result.response?.candidates?.[0]?.content?.parts?.[0]?.text) {
              throw new Error('Gemini response missing text content.');
            }

            let responseText = result.response.candidates[0].content.parts[0].text;
            // Strip markdown code blocks if present
            responseText = responseText.replace(/^```json\n/, '').replace(/^```\n/, '').replace(/\n```$/, '');
            const parsed = JSON.parse(responseText) as GeminiRerankResponse;

            if (!parsed.candidates || !Array.isArray(parsed.candidates)) {
              throw new Error('Gemini response missing candidates array.');
            }

            this.recordSuccess();
            return parsed;
          } catch (error) {
            const isTimeout = this.isTimeoutError(error);

            if (isTimeout) {
              this.logger.warn({ attempt }, 'Gemini request timed out.');
              throw new AbortError(error as Error);
            }

            // Check if it's a parsing error or API error
            const errorMessage = error instanceof Error ? error.message : String(error);
            const isParsingError = errorMessage.includes('JSON') || errorMessage.includes('parse');

            if (isParsingError) {
              this.logger.warn({ attempt, error: errorMessage }, 'Gemini JSON parsing failed.');
              throw new AbortError(error as Error);
            }

            this.logger.warn({ attempt, error: errorMessage }, 'Gemini request attempt failed.');
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
        this.logger.warn({ latencyMs, target: this.config.timeoutMs }, 'Gemini request exceeded timeout budget.');
      }

      return { data, latencyMs };
    } catch (error) {
      const originalError = (error as { originalError?: unknown }).originalError ?? error;

      if (originalError instanceof Error && originalError.message.includes('budget exhausted')) {
        this.logger.warn({ tenantId: options.tenantId }, 'Gemini request skipped due to exhausted budget.');
        return null;
      }

      this.recordFailure(originalError);

      if (this.isTimeoutError(originalError)) {
        this.logger.warn({ tenantId: options.tenantId }, 'Gemini request timed out. Falling back.');
        return null;
      }

      this.logger.error({ error: originalError }, 'Gemini request failed.');
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

    return false;
  }

  async healthCheck(): Promise<GeminiHealthStatus> {
    if (!this.config.enable) {
      return { status: 'disabled', message: 'Gemini disabled via configuration.' } satisfies GeminiHealthStatus;
    }

    if (!this.model) {
      return { status: 'unavailable', message: 'Gemini client not initialised.' } satisfies GeminiHealthStatus;
    }

    if (this.isCircuitOpen()) {
      return {
        status: 'degraded',
        circuitOpen: true,
        failureCount: this.failureCount,
        lastFailureAt: new Date(this.circuitOpenedAt ?? Date.now()).toISOString()
      } satisfies GeminiHealthStatus;
    }

    return { status: 'healthy', failureCount: this.failureCount } satisfies GeminiHealthStatus;
  }

  async close(): Promise<void> {
    // Nothing to close explicitly but method kept for parity with other services.
  }
}
