/**
 * Vector utilities for Phase 12: Natural Language Search
 * @see NLNG-01: Semantic router lite for intent classification
 */

/**
 * Calculate cosine similarity between two vectors.
 * Used for intent classification via embedding comparison.
 */
export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) {
    throw new Error(`Vector length mismatch: ${a.length} vs ${b.length}`);
  }

  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  const denominator = Math.sqrt(normA) * Math.sqrt(normB);
  if (denominator === 0) return 0;

  return dotProduct / denominator;
}

/**
 * Compute average of multiple embeddings.
 * Used to create route embeddings from multiple utterances.
 */
export function averageEmbeddings(embeddings: number[][]): number[] {
  if (embeddings.length === 0) {
    throw new Error('Cannot average empty embeddings array');
  }

  const dimensions = embeddings[0].length;
  const result = new Array(dimensions).fill(0);

  for (const embedding of embeddings) {
    if (embedding.length !== dimensions) {
      throw new Error(`Embedding dimension mismatch: expected ${dimensions}, got ${embedding.length}`);
    }
    for (let i = 0; i < dimensions; i++) {
      result[i] += embedding[i];
    }
  }

  const count = embeddings.length;
  for (let i = 0; i < dimensions; i++) {
    result[i] /= count;
  }

  return result;
}
