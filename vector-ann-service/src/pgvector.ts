import { Client } from 'pg';
import type { PgVectorClient } from './types.js';

export class PostgresPgVectorClient implements PgVectorClient {
  private client: Client;

  constructor() {
    this.client = new Client({
      host: process.env.PGHOST,
      user: process.env.PGUSER,
      password: process.env.PGPASSWORD,
      database: process.env.PGDATABASE,
      port: process.env.PGPORT ? parseInt(process.env.PGPORT, 10) : 5432,
      ssl: process.env.PGSSL === 'true' ? { rejectUnauthorized: false } : undefined
    });
  }

  async connect(): Promise<void> {
    await this.client.connect();
  }

  async disconnect(): Promise<void> {
    await this.client.end();
  }

  async searchANN(embedding: number[], limit: number, filters?: Record<string, unknown>) {
    // NOTE: This assumes an ivfflat index with vector_cosine_ops and a table named candidate_vectors(embedding VECTOR(768))
    const q = `
      SELECT candidate_id,
             1 - (embedding <=> $1::vector) AS similarity_score,
             metadata
      FROM candidate_vectors
      ORDER BY embedding <-> $1::vector
      LIMIT $2;
    `;
    const res = await this.client.query(q, [embedding, limit]);
    return res.rows.map((r: any) => ({
      candidate_id: r.candidate_id,
      similarity_score: Number(r.similarity_score),
      metadata: r.metadata || {}
    }));
  }
}

