import type { Logger } from 'pino';

import type {
  EmbeddingProviderSettings,
  EmbeddingRuntimeSettings
} from './config';
import type { EmbeddingProviderName, EmbeddingVector } from './types';

export interface EmbeddingProvider {
  readonly name: EmbeddingProviderName;
  readonly model: string;
  readonly dimensions: number;
  generateEmbedding(text: string): Promise<EmbeddingVector>;
}

export interface EmbeddingProviderFactoryOptions {
  runtime: EmbeddingRuntimeSettings;
  providers: EmbeddingProviderSettings;
  logger: Logger;
  providerOverride?: EmbeddingProviderName;
}

const INPUT_CHARACTER_LIMIT = 3_000;

class LocalDeterministicProvider implements EmbeddingProvider {
  readonly name: EmbeddingProviderName = 'local';
  readonly model = 'local-deterministic';
  readonly dimensions: number;

  constructor(dimensions: number) {
    this.dimensions = dimensions;
  }

  async generateEmbedding(text: string): Promise<EmbeddingVector> {
    const normalized = text.trim().toLowerCase();
    const vector = Array.from({ length: this.dimensions }, (_, index) => {
      let hash = 0;
      for (let i = 0; i < normalized.length; i += 1) {
        hash = (hash << 5) - hash + normalized.charCodeAt(i);
        hash |= 0;
      }
      return Math.sin(hash + index) * 0.5;
    });

    const magnitude = Math.sqrt(vector.reduce((acc, value) => acc + value * value, 0));
    return magnitude > 0 ? vector.map((value) => value / magnitude) : vector;
  }
}

class VertexAiProvider implements EmbeddingProvider {
  readonly name: EmbeddingProviderName = 'vertex-ai';

  private readonly predictionClient: unknown;
  readonly model: string;
  readonly dimensions: number;

  constructor(
    private readonly logger: Logger,
    private readonly settings: EmbeddingProviderSettings['vertex'],
    runtime: EmbeddingRuntimeSettings
  ) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const vertex = require('@google-cloud/aiplatform');
    const { PredictionServiceClient } = vertex.v1;
    this.predictionClient = new PredictionServiceClient({
      apiEndpoint: `${this.settings.location}-aiplatform.googleapis.com`
    });
    this.model = this.settings.model;
    this.dimensions = runtime.dimensions;
  }

  async generateEmbedding(text: string): Promise<EmbeddingVector> {
    const client = this.predictionClient as {
      predict: (request: Record<string, unknown>) => Promise<Array<Record<string, unknown>>>;
    };

    const trimmed = text.trim().slice(0, INPUT_CHARACTER_LIMIT);
    if (!trimmed) {
      throw new Error('Text payload must not be empty for embedding generation.');
    }

    const endpoint = `projects/${this.settings.projectId}/locations/${this.settings.location}/publishers/google/models/${this.model}`;

    try {
      const [response] = await client.predict({
        endpoint,
        instances: [
          {
            structValue: {
              fields: {
                content: {
                  stringValue: trimmed
                }
              }
            }
          }
        ],
        parameters: {
          structValue: {
            fields: {
              outputDimensionality: {
                numberValue: this.dimensions
              }
            }
          }
        }
      });

      const predictions = (response as any).predictions ?? [];
      const embedding = this.parseEmbeddingFromPrediction(predictions[0]);

      if (!Array.isArray(embedding) || embedding.length === 0) {
        this.logger.error(
          {
            prediction: this.redactPrediction(predictions[0])
          },
          'Vertex AI embedding response returned an empty vector.'
        );
        throw new Error('Vertex AI response did not include an embedding vector.');
      }

      if (embedding.length !== this.dimensions) {
        const message = `Vertex AI embedding dimensionality mismatch. Expected ${this.dimensions}, received ${embedding.length}.`;
        this.logger.error(
          {
            prediction: this.redactPrediction(predictions[0])
          },
          message
        );
        throw new Error(message);
      }

      return embedding as EmbeddingVector;
    } catch (error) {
      this.logger.error({ error }, 'Failed to generate embedding using Vertex AI.');
      throw error;
    }
  }

  private parseEmbeddingFromPrediction(prediction: unknown): number[] {
    if (!prediction || typeof prediction !== 'object') {
      return [];
    }

    const structValue = (prediction as any).structValue;
    const fields = structValue?.fields ?? {};

    const primaryValues = fields.embeddings?.structValue?.fields?.values?.listValue?.values;
    const legacyValues = fields.embeddings?.listValue?.values;

    const candidates = [primaryValues, legacyValues];

    for (const candidate of candidates) {
      if (!Array.isArray(candidate)) {
        continue;
      }

      const vector = candidate
        .map((value) => {
          if (typeof value === 'number') {
            return value;
          }
          if (value && typeof value === 'object') {
            if (typeof (value as any).numberValue === 'number') {
              return (value as any).numberValue;
            }
            const nestedNumber = (value as any).structValue?.fields?.value?.numberValue;
            if (typeof nestedNumber === 'number') {
              return nestedNumber;
            }
          }
          return null;
        })
        .filter((entry): entry is number => typeof entry === 'number');

      if (vector.length > 0) {
        return vector;
      }
    }

    return [];
  }

  private redactPrediction(prediction: unknown): unknown {
    if (!prediction || typeof prediction !== 'object') {
      return prediction;
    }

    try {
      return JSON.parse(
        JSON.stringify(prediction, (_key, value) => {
          if (typeof value === 'string' && value.length > 48) {
            return '[redacted]';
          }
          return value;
        })
      );
    } catch (_error) {
      return '[unserializable prediction]';
    }
  }
}

class TogetherStubProvider implements EmbeddingProvider {
  readonly name: EmbeddingProviderName = 'together';
  readonly model: string;
  readonly dimensions: number;

  constructor(dimensions: number) {
    this.dimensions = dimensions;
    this.model = 'together-stub';
  }

  async generateEmbedding(text: string): Promise<EmbeddingVector> {
    const normalized = text.trim();
    const vector = Array.from({ length: this.dimensions }, (_, index) => {
      let hash = 0;
      for (let i = 0; i < normalized.length; i += 1) {
        hash = (hash << 5) - hash + normalized.charCodeAt(i);
        hash |= 0;
      }
      return Math.cos(hash + index) * 0.5;
    });

    const magnitude = Math.sqrt(vector.reduce((sum, value) => sum + value * value, 0));
    return magnitude > 0 ? vector.map((value) => value / magnitude) : vector;
  }
}

export function createEmbeddingProvider(options: EmbeddingProviderFactoryOptions): EmbeddingProvider {
  const providerName = options.providerOverride ?? options.runtime.provider;

  switch (providerName) {
    case 'vertex-ai':
      return new VertexAiProvider(options.logger.child({ provider: 'vertex-ai' }), options.providers.vertex, options.runtime);
    case 'together':
      if (!options.providers.together.apiKey) {
        options.logger.warn({ provider: 'together' }, 'TOGETHER_API_KEY not configured. Falling back to deterministic stub provider.');
        return new TogetherStubProvider(options.runtime.dimensions);
      }
      return new TogetherStubProvider(options.runtime.dimensions);
    case 'local':
    default:
      return new LocalDeterministicProvider(options.providers.localDimensions || options.runtime.dimensions);
  }
}
