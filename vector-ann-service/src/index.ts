import express from 'express';
import { z } from 'zod';
import { VertexEmbeddingProvider } from './embedding.js';
import { PostgresPgVectorClient } from './pgvector.js';

const app = express();
app.use(express.json({ limit: '1mb' }));

const SearchSchema = z.object({
  query_text: z.string().min(1),
  limit: z.number().min(1).max(200).default(50),
  filters: z.record(z.any()).optional(),
  org_id: z.string().optional()
});

const SkillRequirementSchema = z.object({
  skill: z.string(),
  minimum_confidence: z.number().min(0).max(100).optional(),
  weight: z.number().min(0).max(1).optional(),
  category: z.string().optional()
});

const SkillAwareSchema = z.object({
  text_query: z.string().min(1),
  required_skills: z.array(SkillRequirementSchema).optional(),
  preferred_skills: z.array(SkillRequirementSchema).optional(),
  experience_level: z.enum(['entry','mid','senior','executive']).optional(),
  minimum_overall_confidence: z.number().min(0).max(100).optional(),
  filters: z.record(z.any()).optional(),
  limit: z.number().min(1).max(200).default(20),
  ranking_weights: z.object({
    skill_match: z.number().min(0).max(1).optional(),
    confidence: z.number().min(0).max(1).optional(),
    vector_similarity: z.number().min(0).max(1).optional(),
    experience_match: z.number().min(0).max(1).optional()
  }).optional(),
  org_id: z.string().optional()
});

const embeddingProvider = new VertexEmbeddingProvider();
const pg = new PostgresPgVectorClient();

app.post('/search', async (req, res) => {
  try {
    const input = SearchSchema.parse(req.body);
    const emb = await embeddingProvider.generateEmbedding(input.query_text);
    await pg.connect();
    const ann = await pg.searchANN(emb, input.limit, input.filters);
    await pg.disconnect();
    res.json({ candidates: ann, search_time_ms: 0 });
  } catch (err: any) {
    res.status(400).json({ error: err.message || 'invalid_request' });
  }
});

app.post('/skill-aware-search', async (req, res) => {
  try {
    const input = SkillAwareSchema.parse(req.body);
    const emb = await embeddingProvider.generateEmbedding(input.text_query);
    await pg.connect();
    const ann = await pg.searchANN(emb, (input.limit || 20) * 2, input.filters);
    await pg.disconnect();

    // NOTE: For a complete implementation, fetch candidate structured data and compute
    // skill_match/confidence/experience features. Here we return ANN results as-is.
    const results = ann.map(r => ({
      candidate_id: r.candidate_id,
      similarity_score: r.similarity_score,
      metadata: r.metadata,
      match_reasons: ['semantic match']
    }));
    res.json({ candidates: results, search_time_ms: 0 });
  } catch (err: any) {
    res.status(400).json({ error: err.message || 'invalid_request' });
  }
});

const port = process.env.PORT ? parseInt(process.env.PORT, 10) : 8080;
app.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`Vector ANN service listening on :${port}`);
});

