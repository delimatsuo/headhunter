/**
 * Keyword Search Cloud Function
 * Searches the PostgreSQL sourcing database for candidates by keywords
 * Supports fuzzy matching on names, companies, titles, and full-text search
 */

import { onCall, HttpsError } from "firebase-functions/v2/https";
import { defineSecret } from "firebase-functions/params";
import { z } from "zod";
import { Pool } from 'pg';

const dbPostgresPassword = defineSecret("db-postgres-password");

// Input validation schema
const KeywordSearchInputSchema = z.object({
  query: z.string().min(1).max(500),
  limit: z.number().min(1).max(100).optional().default(50),
});

// Result type for candidates
export interface KeywordSearchCandidate {
  candidate_id: string;
  first_name: string | null;
  last_name: string | null;
  headline: string | null;
  location: string | null;
  linkedin_url: string | null;
  intelligent_analysis: Record<string, any> | null;
  current_company: string | null;
  current_role: string | null;
}

/**
 * Parse query into keywords for search
 * Handles queries like "Andre + Google", "CFO Nubank", "Python Senior"
 */
function parseKeywords(query: string): string[] {
  // Split on common delimiters: +, AND, spaces, commas
  const parts = query
    .replace(/\+/g, ' ')
    .replace(/\bAND\b/gi, ' ')
    .replace(/,/g, ' ')
    .split(/\s+/)
    .map(s => s.trim().toLowerCase())
    .filter(s => s.length > 0);

  return [...new Set(parts)]; // Dedupe
}

/**
 * Keyword search endpoint - searches PostgreSQL sourcing database
 * Returns candidates matching by name, company, title, or full-text
 */
export const keywordSearch = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 60,
    secrets: [dbPostgresPassword],
    vpcConnector: "svpc-us-central1",
    vpcConnectorEgressSettings: "PRIVATE_RANGES_ONLY",
  },
  async (request) => {
    // Validate input
    let validatedInput;
    try {
      validatedInput = KeywordSearchInputSchema.parse(request.data);
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
      }
      throw new HttpsError("invalid-argument", "Invalid request data");
    }

    const { query, limit } = validatedInput;
    const keywords = parseKeywords(query);

    if (keywords.length === 0) {
      return { success: true, candidates: [], total: 0 };
    }

    // Create database connection
    const pool = new Pool({
      host: process.env.PGVECTOR_HOST || "10.159.0.2",
      port: parseInt(process.env.PGVECTOR_PORT || "5432"),
      database: process.env.PGVECTOR_DATABASE || "headhunter",
      user: process.env.PGVECTOR_USER || "postgres",
      password: dbPostgresPassword.value(),
      max: 5,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000,
    });

    try {
      console.log(`[keywordSearch] Query: "${query}", Keywords: ${keywords.join(', ')}, Limit: ${limit}`);

      // Build dynamic search query with fuzzy matching using pg_trgm
      // Strategy: Search across multiple columns with similarity matching
      // 1. Full-text search on search_document (if it exists)
      // 2. Trigram similarity on first_name, last_name
      // 3. ILIKE on company_name and title from experience table

      // First check if pg_trgm extension is available
      const extCheck = await pool.query(
        "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"
      );
      const hasTrgm = extCheck.rows.length > 0;
      console.log(`[keywordSearch] pg_trgm available: ${hasTrgm}`);

      // Build the search query
      // For each keyword, we check multiple columns
      let whereConditions: string[] = [];
      let params: any[] = [];
      let paramIndex = 1;

      for (const keyword of keywords) {
        const keywordConditions: string[] = [];

        if (hasTrgm) {
          // Fuzzy name matching with trigrams (handles typos)
          keywordConditions.push(`similarity(LOWER(COALESCE(c.first_name, '')), $${paramIndex}) > 0.3`);
          keywordConditions.push(`similarity(LOWER(COALESCE(c.last_name, '')), $${paramIndex}) > 0.3`);
          // Fuzzy company matching (use COALESCE for NULL safety)
          keywordConditions.push(`similarity(LOWER(COALESCE(e.company_name, '')), $${paramIndex}) > 0.3`);
          // Fuzzy title matching
          keywordConditions.push(`similarity(LOWER(COALESCE(e.title, '')), $${paramIndex}) > 0.3`);
          params.push(keyword);
          paramIndex++;
        }

        // Also add ILIKE for exact substring matches (faster for short strings)
        // Use COALESCE to handle NULL values from LEFT JOIN
        const likePattern = `%${keyword}%`;
        keywordConditions.push(`LOWER(COALESCE(c.first_name, '')) LIKE $${paramIndex}`);
        keywordConditions.push(`LOWER(COALESCE(c.last_name, '')) LIKE $${paramIndex}`);
        keywordConditions.push(`LOWER(COALESCE(c.headline, '')) LIKE $${paramIndex}`);
        keywordConditions.push(`LOWER(COALESCE(e.company_name, '')) LIKE $${paramIndex}`);
        keywordConditions.push(`LOWER(COALESCE(e.title, '')) LIKE $${paramIndex}`);
        params.push(likePattern);
        paramIndex++;

        // Also search in intelligent_analysis JSON if it exists
        keywordConditions.push(`COALESCE(c.intelligent_analysis::text, '') ILIKE $${paramIndex}`);
        params.push(likePattern);
        paramIndex++;

        // Combine conditions for this keyword with OR
        if (keywordConditions.length > 0) {
          whereConditions.push(`(${keywordConditions.join(' OR ')})`);
        }
      }

      // All keywords must match (AND between keywords)
      const whereClause = whereConditions.length > 0
        ? whereConditions.join(' AND ')
        : 'TRUE';

      params.push(limit);
      const limitParam = `$${paramIndex}`;

      // Query with experience join for searching, and subquery for best role/company
      const sql = `
        SELECT DISTINCT ON (c.id)
          c.id::text as candidate_id,
          c.first_name,
          c.last_name,
          c.headline,
          c.location,
          c.linkedin_url,
          c.intelligent_analysis,
          COALESCE(
            (SELECT company_name FROM sourcing.experience WHERE candidate_id = c.id AND is_current = TRUE LIMIT 1),
            (SELECT company_name FROM sourcing.experience WHERE candidate_id = c.id ORDER BY start_date DESC NULLS LAST LIMIT 1)
          ) as current_company,
          COALESCE(
            (SELECT title FROM sourcing.experience WHERE candidate_id = c.id AND is_current = TRUE LIMIT 1),
            (SELECT title FROM sourcing.experience WHERE candidate_id = c.id ORDER BY start_date DESC NULLS LAST LIMIT 1),
            c.intelligent_analysis->>'current_role',
            NULLIF(SPLIT_PART(c.headline, ' at ', 1), c.headline),
            NULLIF(SPLIT_PART(c.headline, ' @ ', 1), c.headline),
            c.headline
          ) as current_role
        FROM sourcing.candidates c
        LEFT JOIN sourcing.experience e ON e.candidate_id = c.id
        WHERE c.deleted_at IS NULL
          AND c.consent_status != 'opted_out'
          AND (${whereClause})
        ORDER BY c.id
        LIMIT ${limitParam}
      `;

      console.log(`[keywordSearch] Executing query with ${params.length} params`);
      const result = await pool.query(sql, params);
      console.log(`[keywordSearch] Found ${result.rows.length} candidates`);

      // Transform results
      const candidates: KeywordSearchCandidate[] = result.rows.map(row => ({
        candidate_id: row.candidate_id,
        first_name: row.first_name,
        last_name: row.last_name,
        headline: row.headline,
        location: row.location,
        linkedin_url: row.linkedin_url,
        intelligent_analysis: row.intelligent_analysis,
        current_company: row.current_company,
        current_role: row.current_role,
      }));

      return {
        success: true,
        candidates,
        total: candidates.length,
        query: query,
        keywords: keywords,
      };

    } catch (error: any) {
      console.error("[keywordSearch] Error:", error);
      throw new HttpsError("internal", `Search failed: ${error.message}`);
    } finally {
      await pool.end();
    }
  }
);
