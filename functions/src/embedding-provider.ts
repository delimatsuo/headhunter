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
  async generateEmbedding(text: string): Promise<number[]> {
    try {
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
      const [response] = await predictionClient.predict({
        endpoint,
        instances: instances.map((i) => ({ content: { stringValue: i.content } } as any)),
        parameters: Object.fromEntries(
          Object.entries(parameters).map(([k, v]) => [k, { numberValue: v as number }])
        ),
      });
      const pred = (response as any).predictions?.[0];
      const embed = pred?.structValue?.fields?.embeddings?.listValue?.values?.map(
        (v: any) => v.numberValue || 0
      );
      if (Array.isArray(embed) && embed.length === 768) return embed;
      throw new Error("Vertex embeddings response missing or invalid");
    } catch (err) {
      // Do not return mock/deterministic data in production paths
      throw err instanceof Error ? err : new Error("Vertex embeddings unavailable");
    }
  }
}

export function getEmbeddingProvider(): EmbeddingProvider {
  const provider = (process.env.EMBEDDING_PROVIDER || "vertex").toLowerCase();
  switch (provider) {
    case "local":
      return new LocalDeterministicProvider();
    case "vertex":
    default:
      return new VertexProvider();
  }
}
