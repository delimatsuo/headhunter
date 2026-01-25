/**
 * Embedding Backfill Worker
 *
 * Pre-computes embeddings for all candidates in the database.
 * This eliminates on-demand embedding generation during search.
 *
 * Usage: npx ts-node scripts/embedding-backfill-worker.ts [--batch-size=100] [--concurrency=10]
 */

import { Pool } from 'pg';
import { GoogleGenerativeAI } from '@google/generative-ai';

interface Config {
  batchSize: number;
  concurrency: number;
  dryRun: boolean;
}

interface CandidateRow {
  candidate_id: string;
  tenant_id: string;
  full_name: string | null;
  current_title: string | null;
  headline: string | null;
  skills: string[] | null;
}

async function generateEmbedding(
  genai: GoogleGenerativeAI,
  text: string
): Promise<number[]> {
  const model = genai.getGenerativeModel({ model: 'text-embedding-004' });
  const result = await model.embedContent(text);
  return result.embedding.values;
}

function buildEmbeddingText(candidate: CandidateRow): string {
  const parts: string[] = [];
  if (candidate.current_title) parts.push(candidate.current_title);
  if (candidate.headline) parts.push(candidate.headline);
  if (candidate.skills?.length) parts.push(candidate.skills.join(', '));
  return parts.join(' | ') || 'No details available';
}

async function processBatch(
  pool: Pool,
  genai: GoogleGenerativeAI,
  candidates: CandidateRow[],
  config: Config
): Promise<{ processed: number; errors: number }> {
  let processed = 0;
  let errors = 0;

  // Process with concurrency limit
  const chunks: CandidateRow[][] = [];
  for (let i = 0; i < candidates.length; i += config.concurrency) {
    chunks.push(candidates.slice(i, i + config.concurrency));
  }

  for (const chunk of chunks) {
    const results = await Promise.allSettled(
      chunk.map(async (candidate) => {
        const text = buildEmbeddingText(candidate);
        const embedding = await generateEmbedding(genai, text);

        if (!config.dryRun) {
          await pool.query(
            `INSERT INTO search.candidate_embeddings
              (tenant_id, entity_id, embedding, embedding_text, model_version, chunk_type, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (tenant_id, entity_id, chunk_type)
            DO UPDATE SET
              embedding = EXCLUDED.embedding,
              embedding_text = EXCLUDED.embedding_text,
              model_version = EXCLUDED.model_version,
              updated_at = NOW()`,
            [candidate.tenant_id, candidate.candidate_id, JSON.stringify(embedding), text, 'text-embedding-004', 'default']
          );
        }

        return candidate.candidate_id;
      })
    );

    for (const result of results) {
      if (result.status === 'fulfilled') {
        processed++;
      } else {
        errors++;
        console.error('Error processing candidate:', result.reason);
      }
    }

    // Rate limiting: 60 requests per minute for Gemini API
    await new Promise(resolve => setTimeout(resolve, config.concurrency * 100));
  }

  return { processed, errors };
}

async function main() {
  // Parse arguments
  const args = process.argv.slice(2);
  const config: Config = {
    batchSize: parseInt(args.find(a => a.startsWith('--batch-size='))?.split('=')[1] ?? '100'),
    concurrency: parseInt(args.find(a => a.startsWith('--concurrency='))?.split('=')[1] ?? '10'),
    dryRun: args.includes('--dry-run')
  };

  console.log('Embedding Backfill Worker starting with config:', config);

  // Initialize clients
  const pool = new Pool({
    host: process.env.PGVECTOR_HOST ?? '127.0.0.1',
    port: parseInt(process.env.PGVECTOR_PORT ?? '5432'),
    database: process.env.PGVECTOR_DATABASE ?? 'headhunter',
    user: process.env.PGVECTOR_USER ?? 'postgres',
    password: process.env.PGVECTOR_PASSWORD ?? ''
  });

  const genai = new GoogleGenerativeAI(process.env.GEMINI_API_KEY ?? '');

  try {
    // Count total candidates
    const countResult = await pool.query(
      'SELECT COUNT(*) as total FROM search.candidate_profiles'
    );
    const total = parseInt(countResult.rows[0].total);
    console.log(`Total candidates to process: ${total}`);

    // Process in batches
    let offset = 0;
    let totalProcessed = 0;
    let totalErrors = 0;

    while (offset < total) {
      const batchResult = await pool.query<CandidateRow>(
        `SELECT candidate_id, tenant_id, full_name, current_title, headline, skills
        FROM search.candidate_profiles
        ORDER BY candidate_id
        LIMIT $1 OFFSET $2`,
        [config.batchSize, offset]
      );

      if (batchResult.rows.length === 0) break;

      console.log(`Processing batch ${offset / config.batchSize + 1} (${offset}-${offset + batchResult.rows.length})...`);

      const { processed, errors } = await processBatch(pool, genai, batchResult.rows, config);
      totalProcessed += processed;
      totalErrors += errors;

      console.log(`Batch complete. Total progress: ${totalProcessed}/${total} (${errors} errors)`);

      offset += config.batchSize;
    }

    console.log(`\nBackfill complete!`);
    console.log(`Processed: ${totalProcessed}`);
    console.log(`Errors: ${totalErrors}`);
    console.log(`Success rate: ${((totalProcessed / (totalProcessed + totalErrors)) * 100).toFixed(1)}%`);

  } finally {
    await pool.end();
  }
}

main().catch(console.error);
