export interface EmbeddingProvider {
  generateEmbedding(text: string): Promise<number[]>;
  name: string;
}

class LocalDeterministicProvider implements EmbeddingProvider {
  name = "local";
  async generateEmbedding(text: string): Promise<number[]> {
    const dim = 768;
    const vec = Array.from({ length: dim }, (_, i) => {
      let hash = 0;
      for (let j = 0; j < Math.min(text.length, 100); j++) {
        hash = (hash << 5) - hash + text.charCodeAt(j);
        hash |= 0;
      }
      return Math.sin(hash + i) * 0.5;
    });
    const mag = Math.sqrt(vec.reduce((s, v) => s + v * v, 0));
    return vec.map((v) => v / (mag || 1));
  }
}

class VertexProvider implements EmbeddingProvider {
  name = "vertex";

  private async generateEmbeddingWithRetry(text: string, retries = 3): Promise<number[]> {
    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        return await this.callVertexAPI(text);
      } catch (err: any) {
        const isRetryable = err?.code === 4 || // DEADLINE_EXCEEDED
          err?.code === 14 || // UNAVAILABLE
          err?.message?.includes('DEADLINE_EXCEEDED');

        if (isRetryable && attempt < retries) {
          console.log(`Vertex embedding attempt ${attempt} failed, retrying in ${attempt * 2}s...`);
          await new Promise(resolve => setTimeout(resolve, attempt * 2000));
          continue;
        }
        throw err;
      }
    }
    throw new Error("Max retries exceeded for Vertex embedding");
  }

  private async callVertexAPI(text: string): Promise<number[]> {
    const { PredictionServiceClient } = require("@google-cloud/aiplatform").v1;
    const projectId = process.env.GOOGLE_CLOUD_PROJECT || "headhunter-ai-0088";
    const location = "us-central1";
    const model = "text-embedding-004";
    const predictionClient = new PredictionServiceClient({
      apiEndpoint: `${location}-aiplatform.googleapis.com`,
    });
    const endpoint = `projects/${projectId}/locations/${location}/publishers/google/models/${model}`;
    const instances = [{ content: text.substring(0, 3000) }];
    const parameters = { outputDimensionality: 768 } as const;

    // Add timeout to prevent DEADLINE_EXCEEDED
    const [response] = await predictionClient.predict({
      endpoint,
      instances: instances.map((i) => ({
        structValue: {
          fields: {
            content: { stringValue: i.content }
          }
        }
      })),
      parameters: {
        structValue: {
          fields: Object.fromEntries(
            Object.entries(parameters).map(([k, v]) => [k, { numberValue: v as number }])
          )
        }
      },
    }, {
      timeout: 120000, // 2 minute timeout
    });

    const pred = (response as any).predictions?.[0];
    const embeddingsStruct = pred?.structValue?.fields?.embeddings?.structValue?.fields;
    const valuesList = embeddingsStruct?.values?.listValue?.values;
    const embed = valuesList?.map((v: any) => v.numberValue || 0);

    if (Array.isArray(embed) && embed.length === 768) return embed;
    throw new Error("Vertex embeddings response missing or invalid");
  }

  async generateEmbedding(text: string): Promise<number[]> {
    try {
      return await this.generateEmbeddingWithRetry(text);
    } catch (err) {
      // Do not return mock/deterministic data in production paths
      throw err instanceof Error ? err : new Error("Vertex embeddings unavailable");
    }
  }
}

class TogetherStubProvider implements EmbeddingProvider {
  name = "together";
  async generateEmbedding(text: string): Promise<number[]> {
    // Deterministic 768-dim placeholder to satisfy tests; real Together embeddings
    // are generated in Python processors per PRD.
    const dim = 768;
    const vec = Array.from({ length: dim }, (_, i) => {
      let hash = 0;
      for (let j = 0; j < Math.min(text.length, 100); j++) {
        hash = (hash << 5) - hash + text.charCodeAt(j);
        hash |= 0;
      }
      return Math.cos(hash + i) * 0.5;
    });
    const mag = Math.sqrt(vec.reduce((s, v) => s + v * v, 0));
    return vec.map((v) => v / (mag || 1));
  }
}

export function getEmbeddingProvider(): EmbeddingProvider {
  const provider = (process.env.EMBEDDING_PROVIDER || "vertex").toLowerCase();
  switch (provider) {
    case "local":
      return new LocalDeterministicProvider();
    case "together":
      return new TogetherStubProvider();
    case "vertex":
    default:
      return new VertexProvider();
  }
}
