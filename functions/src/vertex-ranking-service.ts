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
    career_trajectory?: string;  // Added: work history summary
}

interface RankedCandidate {
    candidate_id: string;
    rank_score: number;
    rank_position: number;
}

interface JobContext {
    function: string;      // product, engineering, data, etc.
    level: string;         // c-level, vp, director, etc.
    title?: string;        // CTO, CPO, VP Engineering
    targetCompanies?: string[];
}

interface RankingOptions {
    topN?: number;
    model?: string;
    jobContext?: JobContext;  // Added: hiring logic context
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
                query: this.formatJobQuery(jobDescription, options.jobContext),
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
     * Format job description for ranking query with hiring logic context
     */
    private formatJobQuery(jobDescription: string, jobContext?: JobContext): string {
        const parts: string[] = [];

        // Add hiring logic based on job context
        if (jobContext) {
            const hiringLogic = this.getHiringLogic(jobContext);
            if (hiringLogic) {
                parts.push(hiringLogic);
                parts.push('---');
            }
        }

        // Truncate job description to reasonable length
        const maxDescLength = 1500;
        const truncatedDesc = jobDescription.length > maxDescLength
            ? jobDescription.slice(0, maxDescLength) + '...'
            : jobDescription;

        parts.push(`JOB DESCRIPTION:\n${truncatedDesc}`);

        return parts.join('\n\n');
    }

    /**
     * Generate hiring logic guidance based on job level and function
     */
    private getHiringLogic(jobContext: JobContext): string {
        const { function: func, level, title } = jobContext;
        const roleTitle = title || `${level} ${func}`;

        // Executive-level hiring logic
        if (level === 'c-level' || level === 'vp') {
            return `RANKING CRITERIA for ${roleTitle.toUpperCase()}:

STRONGEST MATCHES (rank highest):
- Current or former C-level executives in ${func} (CTO, CPO, CIO, etc.)
- VPs with 15+ years experience who are ready for next step
- Founders/Co-founders of successful tech companies

STRONG MATCHES (rank high):  
- Directors with 15+ years who have P&L or large team responsibility
- Former C-levels now in advisory or consulting roles
- Executive-track leaders at FAANG/tier-1 companies

CONSIDER (trajectory matters):
- Senior Directors stepping up to exec level
- Former VPs/Directors who moved to Principal/Staff roles (strategic career move)
- Leaders with right experience but at smaller companies

RANK LOWER:
- Engineering Managers without executive experience
- Individual contributors (Staff Engineers, Principal Engineers)
- People whose experience is in wrong function (e.g., Data Science director for CTO role)

IMPORTANT: Consider career TRAJECTORY, not just current title. Someone who was VP Engineering and is now Principal Engineer may be strategically positioned for the right opportunity.`;
        }

        // Director-level hiring logic
        if (level === 'director') {
            return `RANKING CRITERIA for ${roleTitle.toUpperCase()}:

STRONGEST MATCHES:
- Current Directors in ${func}
- VPs looking for specific Director-level challenge
- Senior Managers with 10+ years ready for promotion

STRONG MATCHES:
- Heads of departments at growing startups
- Former Directors now in IC roles
- Tech Leads with significant management experience

RANK LOWER:
- Early-career managers (< 5 years management)
- Individual contributors without leadership experience
- Wrong function entirely`;
        }

        // Manager-level hiring logic
        if (level === 'manager') {
            return `RANKING CRITERIA for ${roleTitle.toUpperCase()}:

STRONGEST MATCHES:
- Current Managers in ${func}
- Senior ICs transitioning to management
- Tech Leads with team leadership experience

STRONG MATCHES:
- Team Leads at top companies
- Senior engineers with mentorship experience

RANK LOWER:
- Junior candidates
- People with no evidence of leadership`;
        }

        // Default/IC level logic
        return `RANKING CRITERIA for ${roleTitle.toUpperCase()}:

Rank candidates based on:
1. Relevant experience in ${func}
2. Skills matching the job requirements
3. Company pedigree and growth trajectory
4. Career progression and ambition`;
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
