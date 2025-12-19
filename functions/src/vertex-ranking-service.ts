/**
 * Vertex AI Ranking Service
 * 
 * Uses Google's Discovery Engine Ranking API for cross-encoder style reranking.
 * This provides much higher accuracy than bi-encoder similarity alone.
 * 
 * Pricing: $1 per 1,000 queries (up to 200 docs per query)
 * Latency: ~200-500ms for 50 documents
 * 
 * API Reference: https://cloud.google.com/generative-ai-app-builder/docs/ranking
 */

import { RankServiceClient, protos } from '@google-cloud/discoveryengine';

// Types
interface CandidateForRanking {
    candidate_id: string;
    name: string;
    current_role: string;
    years_experience: number;
    skills: string[];
    companies: string[];
    summary?: string;
}

interface RankedCandidate {
    candidate_id: string;
    rank_score: number;
    rank_position: number;
}

interface RankingOptions {
    topN?: number;
    model?: string;
}

export class VertexRankingService {
    private client: RankServiceClient | null = null;
    private projectId: string;

    constructor(projectId?: string) {
        this.projectId = projectId || process.env.GCLOUD_PROJECT || process.env.GOOGLE_CLOUD_PROJECT || '';
    }

    /**
     * Initialize the ranking client
     */
    private async getClient(): Promise<RankServiceClient> {
        if (!this.client) {
            this.client = new RankServiceClient();
        }
        return this.client;
    }

    /**
     * Rerank candidates based on relevance to the job description
     */
    async rerank(
        jobDescription: string,
        candidates: CandidateForRanking[],
        options: RankingOptions = {}
    ): Promise<RankedCandidate[]> {
        const topN = options.topN || 50;
        const startTime = Date.now();

        if (candidates.length === 0) {
            return [];
        }

        try {
            const client = await this.getClient();

            // Format candidates as RankingRecords
            // Each record needs: id, title, content (title and content are used for ranking)
            const records: protos.google.cloud.discoveryengine.v1.IRankingRecord[] =
                candidates.slice(0, 100).map((c) => ({
                    id: c.candidate_id,
                    title: `${c.name} - ${c.current_role}`,
                    content: this.formatCandidateContent(c)
                }));

            // Use the ranking_config_path helper to construct the path
            const rankingConfig = client.rankingConfigPath(
                this.projectId,
                'global',
                'default_ranking_config'
            );

            console.log(`[VertexRanking] Calling API with ${records.length} candidates, project: ${this.projectId}`);

            const request: protos.google.cloud.discoveryengine.v1.IRankRequest = {
                rankingConfig: rankingConfig,
                model: options.model || 'semantic-ranker-default@latest',
                query: this.formatJobQuery(jobDescription),
                records: records,
                topN: Math.min(topN, records.length)
            };

            const [response] = await client.rank(request);

            const latency = Date.now() - startTime;
            console.log(`[VertexRanking] Completed in ${latency}ms, returned ${response.records?.length || 0} results`);

            // Map response to our format
            // The API returns records sorted by relevance with scores
            return (response.records || []).map((record, idx) => ({
                candidate_id: record.id || '',
                rank_score: record.score || 0,
                rank_position: idx + 1
            }));

        } catch (error: any) {
            console.error('[VertexRanking] API failed:', error.message);
            console.error('[VertexRanking] Full error:', error);

            // Re-throw so caller can handle fallback
            throw error;
        }
    }

    /**
     * Format candidate profile for ranking content field
     */
    private formatCandidateContent(candidate: CandidateForRanking): string {
        const parts = [
            `Experience: ${candidate.years_experience} years`,
        ];

        if (candidate.skills && candidate.skills.length > 0) {
            parts.push(`Key Skills: ${candidate.skills.slice(0, 10).join(', ')}`);
        }

        if (candidate.companies && candidate.companies.length > 0) {
            parts.push(`Companies: ${candidate.companies.slice(0, 5).join(', ')}`);
        }

        if (candidate.summary) {
            parts.push(`Summary: ${candidate.summary.slice(0, 300)}`);
        }

        return parts.join('. ');
    }

    /**
     * Format job description for ranking query
     */
    private formatJobQuery(jobDescription: string): string {
        // Truncate to reasonable length for ranking
        const maxLength = 2000;
        if (jobDescription.length > maxLength) {
            return jobDescription.slice(0, maxLength) + '...';
        }
        return jobDescription;
    }

    /**
     * Check if the ranking API is available
     */
    async isAvailable(): Promise<boolean> {
        try {
            const client = await this.getClient();
            return !!client;
        } catch (error) {
            console.warn('[VertexRanking] API not available:', error);
            return false;
        }
    }
}

// Singleton instance
let rankingServiceInstance: VertexRankingService | null = null;

export function getVertexRankingService(): VertexRankingService {
    if (!rankingServiceInstance) {
        rankingServiceInstance = new VertexRankingService();
    }
    return rankingServiceInstance;
}
