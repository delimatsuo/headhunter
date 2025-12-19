/**
 * Agentic Engine
 * 
 * The next-generation intelligent search engine that uses deep reasoning:
 * 
 * 1. DEEP JOB ANALYSIS - Understands the strategic problem, not just keywords
 * 2. MULTI-MODAL RETRIEVAL - Combines vector, structured, and inferred signals
 * 3. COMPARATIVE REASONING - Ranks by comparing candidates against each other
 * 4. INSIGHT GENERATION - Explains WHY each candidate fits (or doesn't)
 * 
 * This engine trades speed for depth, providing recruiter-level insights.
 */

import {
    IAIEngine,
    JobDescription,
    SearchOptions,
    SearchResult,
    CandidateMatch,
    JobAnalysis
} from './types';
import { GoogleGenerativeAI } from '@google/generative-ai';

// Will use environment config
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || '';

export class AgenticEngine implements IAIEngine {
    private genAI: GoogleGenerativeAI | null = null;

    getName(): string {
        return 'agentic';
    }

    getLabel(): string {
        return '🧠 Deep Analysis';
    }

    getDescription(): string {
        return 'Comparative reasoning with detailed insights. Thorough and explanatory.';
    }

    private getModel() {
        if (!this.genAI) {
            this.genAI = new GoogleGenerativeAI(GEMINI_API_KEY);
        }
        return this.genAI.getGenerativeModel({ model: 'gemini-2.0-flash' });
    }

    async search(job: JobDescription, options?: SearchOptions): Promise<SearchResult> {
        const startTime = Date.now();

        if (options?.onProgress) {
            options.onProgress('Understanding role requirements deeply...');
        }

        // ===== STAGE 1: Deep Job Analysis =====
        const jobAnalysis = await this.analyzeJob(job);
        console.log('Job Analysis:', JSON.stringify(jobAnalysis, null, 2));

        if (options?.onProgress) {
            options.onProgress(`Identified: ${jobAnalysis.leadership_style} ${jobAnalysis.level} in ${jobAnalysis.function}`);
        }

        // ===== STAGE 2: Retrieve Candidates =====
        // For now, we'll use the same vector search as legacy
        // In the future, this can incorporate career path matching
        if (options?.onProgress) {
            options.onProgress('Finding candidates matching ideal profile...');
        }

        // PLACEHOLDER: Will call actual vector search
        const candidates: any[] = [];

        if (options?.onProgress) {
            options.onProgress('Evaluating candidates with detailed reasoning...');
        }

        // ===== STAGE 3: Comparative Reranking =====
        const rankedCandidates = await this.comparativeRank(candidates, jobAnalysis);

        // ===== STAGE 4: Generate Insights =====
        const matchesWithInsights = this.addInsights(rankedCandidates, jobAnalysis);

        return {
            matches: matchesWithInsights,
            total_candidates: candidates.length,
            query_time_ms: Date.now() - startTime,
            engine_used: this.getName(),
            engine_version: '1.0.0',
            metadata: {
                job_analysis: jobAnalysis,
                ranking_explanation: 'Candidates ranked by comparative fit analysis with deep reasoning',
                search_strategy: 'deep_analysis + comparative_reasoning'
            }
        };
    }

    // ============================================================================
    // STAGE 1: Deep Job Analysis
    // ============================================================================

    private async analyzeJob(job: JobDescription): Promise<JobAnalysis> {
        const prompt = `
You are an expert executive recruiter with 20 years of experience. Analyze this job deeply.

JOB TITLE: ${job.title || 'Not specified'}
JOB DESCRIPTION:
${job.description}

REQUIRED SKILLS: ${(job.required_skills || []).join(', ') || 'Not specified'}
EXPERIENCE REQUIRED: ${job.min_experience || 0}-${job.max_experience || 20} years

Provide a structured analysis in JSON format:

{
  "core_problem": "What strategic problem is this person solving? (1-2 sentences)",
  "success_indicators": ["What does success look like in 1 year?", "List 3-4 specific outcomes"],
  "function": "engineering | product | data | sales | marketing | finance | hr | operations | design | general",
  "level": "c-suite | vp | director | manager | ic",
  "leadership_style": "builder | scaler | turnaround | operator",
  "must_haves": ["Non-negotiable requirement 1", "Non-negotiable requirement 2"],
  "nice_to_haves": ["Bonus qualification 1", "Bonus qualification 2"],
  "red_flags": ["What would disqualify a candidate?", "List 2-3 specific red flags"],
  "company_stage": "startup | growth | enterprise",
  "industry_context": "Brief description of industry context",
  "ideal_trajectory": "What career path leads to success in this role?"
}

Respond ONLY with the JSON object, no additional text.
`;

        try {
            const model = this.getModel();
            const result = await model.generateContent(prompt);
            const text = result.response.text();

            // Parse JSON from response
            const jsonMatch = text.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                return JSON.parse(jsonMatch[0]) as JobAnalysis;
            }
        } catch (error) {
            console.error('Error analyzing job:', error);
        }

        // Fallback to basic analysis
        return this.basicJobAnalysis(job);
    }

    private basicJobAnalysis(job: JobDescription): JobAnalysis {
        const title = (job.title || '').toLowerCase();

        return {
            core_problem: 'Lead and grow the team',
            success_indicators: ['Team growth', 'Delivery improvement', 'Strategic alignment'],
            function: this.parseFunction(title),
            level: this.parseLevel(title),
            leadership_style: 'builder',
            must_haves: job.required_skills || [],
            nice_to_haves: [],
            red_flags: ['Frequent job changes', 'No relevant experience'],
            company_stage: 'growth',
            industry_context: 'Technology',
            ideal_trajectory: 'Senior IC → Manager → Director → VP'
        };
    }

    // ============================================================================
    // STAGE 3: Comparative Reranking
    // ============================================================================

    private async comparativeRank(
        candidates: any[],
        jobAnalysis: JobAnalysis
    ): Promise<any[]> {
        if (candidates.length === 0) return [];

        // Take top 20 for deep analysis
        const topCandidates = candidates.slice(0, 20);

        const candidateSummaries = topCandidates.map((c, i) => {
            const profile = c.profile || {};
            return `[${i + 1}] ${profile.name || 'Unknown'}
   Title: ${profile.current_role || profile.current_title || 'Unknown'}
   Experience: ${profile.years_experience || 'Unknown'} years
   Companies: ${(profile.companies || []).slice(0, 3).join(', ') || 'Unknown'}
   Skills: ${(profile.skills || []).slice(0, 5).join(', ') || 'Unknown'}`;
        }).join('\n\n');

        const prompt = `
You are evaluating candidates for a ${jobAnalysis.level} ${jobAnalysis.function} role.

ROLE CONTEXT:
- Core Problem: ${jobAnalysis.core_problem}
- Leadership Style Needed: ${jobAnalysis.leadership_style}
- Must-Haves: ${jobAnalysis.must_haves.join(', ')}
- Red Flags: ${jobAnalysis.red_flags.join(', ')}

CANDIDATES:
${candidateSummaries}

For EACH candidate, provide a brief assessment in JSON format:
{
  "rankings": [
    {
      "candidate_index": 1,
      "fit_score": 85,
      "top_strength": "One sentence about their biggest strength for THIS role",
      "top_concern": "One sentence about the main concern or risk",
      "recommendation": "Strong Fit | Good Fit | Weak Fit | Not Recommended"
    }
  ],
  "ranking_rationale": "Brief explanation of why top candidate is ranked #1"
}

Respond ONLY with the JSON object.
`;

        try {
            const model = this.getModel();
            const result = await model.generateContent(prompt);
            const text = result.response.text();

            const jsonMatch = text.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                const rankings = JSON.parse(jsonMatch[0]);

                // Apply rankings to candidates
                return topCandidates.map((candidate, i) => {
                    const ranking = rankings.rankings?.find((r: any) => r.candidate_index === i + 1);
                    return {
                        ...candidate,
                        agentic_score: ranking?.fit_score || 50,
                        agentic_strength: ranking?.top_strength || '',
                        agentic_concern: ranking?.top_concern || '',
                        agentic_recommendation: ranking?.recommendation || 'Unknown'
                    };
                }).sort((a, b) => b.agentic_score - a.agentic_score);
            }
        } catch (error) {
            console.error('Error in comparative ranking:', error);
        }

        return topCandidates;
    }

    // ============================================================================
    // STAGE 4: Add Insights
    // ============================================================================

    private addInsights(candidates: any[], jobAnalysis: JobAnalysis): CandidateMatch[] {
        return candidates.map((c, index) => {
            const profile = c.profile || {};

            return {
                candidate_id: c.id || c.candidate_id || '',
                candidate: c,
                score: c.agentic_score || c.overall_score || 50,
                rationale: {
                    overall_assessment: c.agentic_strength ||
                        `${profile.name || 'Candidate'} has relevant experience in ${jobAnalysis.function}`,
                    strengths: [
                        c.agentic_strength || 'Relevant background',
                        `${profile.years_experience || 'Unknown'} years of experience`
                    ],
                    concerns: c.agentic_concern ? [c.agentic_concern] : [],
                    interview_questions: this.generateInterviewQuestions(c, jobAnalysis)
                },
                match_metadata: {
                    vector_score: c.overall_score,
                    rerank_score: c.agentic_score
                }
            };
        });
    }

    private generateInterviewQuestions(candidate: any, jobAnalysis: JobAnalysis): string[] {
        // Generate role-specific interview questions
        const profile = candidate.profile || {};
        const questions: string[] = [];

        // Question about leadership style
        if (jobAnalysis.leadership_style === 'builder') {
            questions.push(`Tell me about a time you built a ${jobAnalysis.function} team from scratch.`);
        } else if (jobAnalysis.leadership_style === 'scaler') {
            questions.push(`How have you scaled a ${jobAnalysis.function} team from 10 to 50+ people?`);
        }

        // Question about core problem
        questions.push(`How would you approach: ${jobAnalysis.core_problem}?`);

        // Question about potential concern
        if (candidate.agentic_concern) {
            questions.push(`I noticed ${candidate.agentic_concern}. Can you tell me more about that?`);
        }

        return questions.slice(0, 3);
    }

    // ============================================================================
    // HELPER FUNCTIONS
    // ============================================================================

    private parseLevel(title: string): 'c-suite' | 'vp' | 'director' | 'manager' | 'ic' {
        const t = title.toLowerCase();
        if (t.includes('chief') || t.match(/\bc[etpfo]o\b/) || t.includes('president')) return 'c-suite';
        if (t.includes('vp') || t.includes('vice president')) return 'vp';
        if (t.includes('director') || t.includes('head of')) return 'director';
        if (t.includes('manager') || t.includes('lead')) return 'manager';
        return 'ic';
    }

    private parseFunction(title: string): JobAnalysis['function'] {
        const t = title.toLowerCase();

        // Handle C-suite abbreviations
        if (t.includes('cto') || t.match(/chief\s+tech/)) return 'engineering';
        if (t.includes('cpo') || t.match(/chief\s+product/)) return 'product';
        if (t.includes('cdo') || t.match(/chief\s+data/)) return 'data';
        if (t.includes('cro') || t.match(/chief\s+revenue/)) return 'sales';
        if (t.includes('cmo') || t.match(/chief\s+market/)) return 'marketing';
        if (t.includes('coo') || t.match(/chief\s+operat/)) return 'operations';
        if (t.includes('chro') || t.match(/chief\s+(people|human)/)) return 'hr';
        if (t.includes('cfo') || t.match(/chief\s+finan/)) return 'finance';

        // General keywords
        if (t.includes('engineer') || t.includes('software')) return 'engineering';
        if (t.includes('product')) return 'product';
        if (t.includes('data') || t.includes('scientist')) return 'data';
        if (t.includes('sales') || t.includes('revenue')) return 'sales';
        if (t.includes('marketing') || t.includes('growth')) return 'marketing';
        if (t.includes('finance')) return 'finance';
        if (t.includes('hr') || t.includes('people')) return 'hr';
        if (t.includes('operations')) return 'operations';
        if (t.includes('design') || t.includes('ux')) return 'design';
        return 'general';
    }
}
