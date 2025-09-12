import type { EmbeddingProvider } from './types.js';

// Explicitly avoid mock/deterministic fallbacks. Implement real Vertex call or throw.
export class VertexEmbeddingProvider implements EmbeddingProvider {
  async generateEmbedding(_text: string): Promise<number[]> {
    // Not implemented in this skeleton; do not return mock data.
    throw new Error('Vertex embedding provider not configured');
  }
}
