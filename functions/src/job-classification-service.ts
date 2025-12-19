/**
 * Job Classification Service
 * 
 * Uses Gemini LLM to classify job titles and descriptions into standardized
 * functions, levels, and domains. This replaces brittle keyword matching
 * with semantic understanding.
 */

import { geminiModel } from './gemini-client';

// Job function categories
export type JobFunction =
    | 'product'
    | 'engineering'
    | 'data'
    | 'design'
    | 'sales'
    | 'marketing'
    | 'hr'
    | 'finance'
    | 'operations'
    | 'general';

// Seniority levels
export type JobLevel =
    | 'intern'
    | 'junior'
    | 'mid'
    | 'senior'
    | 'staff'
    | 'principal'
    | 'manager'
    | 'director'
    | 'vp'
    | 'c-level';

export interface JobClassification {
    function: JobFunction;
    level: JobLevel;
    domain: string[];
    confidence: number;
}

export interface CandidateClassification extends JobClassification {
    candidate_id: string;
}

// Level numeric mapping for distance calculation
const LEVEL_ORDER: Record<JobLevel, number> = {
    'intern': 1,
    'junior': 2,
    'mid': 3,
    'senior': 4,
    'staff': 5,
    'principal': 6,
    'manager': 4,  // Same as senior (different track)
    'director': 5,
    'vp': 6,
    'c-level': 7
};

// Similar functions (for partial matching)
const SIMILAR_FUNCTIONS: Record<JobFunction, JobFunction[]> = {
    'product': ['design', 'data'],
    'engineering': ['data'],
    'data': ['engineering', 'product'],
    'design': ['product'],
    'sales': ['marketing'],
    'marketing': ['sales'],
    'hr': [],
    'finance': [],
    'operations': [],
    'general': []
};

class JobClassificationService {
    private cache: Map<string, JobClassification> = new Map();

    /**
     * Classify a target job from title and description
     */
    async classifyJob(jobTitle: string, jobDescription?: string): Promise<JobClassification> {
        const cacheKey = `job:${jobTitle}:${(jobDescription || '').slice(0, 100)}`;

        if (this.cache.has(cacheKey)) {
            return this.cache.get(cacheKey)!;
        }

        const prompt = `Classify this job into standardized categories.

Job Title: ${jobTitle}
${jobDescription ? `Description (first 500 chars): ${jobDescription.slice(0, 500)}` : ''}

Return ONLY valid JSON (no markdown, no explanation):
{
  "function": "product" | "engineering" | "data" | "design" | "sales" | "marketing" | "hr" | "finance" | "operations" | "general",
  "level": "intern" | "junior" | "mid" | "senior" | "staff" | "principal" | "manager" | "director" | "vp" | "c-level",
  "domain": ["industry1", "industry2"],
  "confidence": 0.0 to 1.0
}

Important:
- CPO, Chief Product Officer, VP Product, Director of Product = function: "product"
- CTO, Chief Technology Officer, Engineering Manager = function: "engineering"
- Data Scientist, Analytics = function: "data"
- CEO, COO with no specific domain = function: "general"
- Portuguese titles like "Gerente de Produto" = function: "product"
- "Engenheiro de Software" = function: "engineering"`;

        try {
            const result = await geminiModel.generateContent(prompt);
            const text = result.response.candidates?.[0]?.content?.parts?.[0]?.text || '';

            // Extract JSON from response (handle potential markdown wrapping)
            const jsonMatch = text.match(/\{[\s\S]*\}/);
            if (!jsonMatch) {
                console.error('[JobClassification] Failed to parse response:', text);
                return this.getDefaultClassification();
            }

            const classification = JSON.parse(jsonMatch[0]) as JobClassification;
            this.cache.set(cacheKey, classification);

            console.log(`[JobClassification] Classified "${jobTitle}" as:`, classification);
            return classification;
        } catch (error: any) {
            console.error('[JobClassification] Error:', error.message);
            return this.getDefaultClassification();
        }
    }

    /**
     * Classify multiple candidates in a single batch call
     * More efficient than individual calls
     */
    async classifyCandidatesBatch(
        candidates: Array<{
            candidate_id: string;
            current_role?: string;
            experience?: string;
        }>
    ): Promise<Map<string, JobClassification>> {
        const results = new Map<string, JobClassification>();

        // Check cache first, collect uncached
        const uncached: typeof candidates = [];
        for (const c of candidates) {
            const cacheKey = `candidate:${c.candidate_id}`;
            if (this.cache.has(cacheKey)) {
                results.set(c.candidate_id, this.cache.get(cacheKey)!);
            } else {
                uncached.push(c);
            }
        }

        if (uncached.length === 0) {
            return results;
        }

        // Format candidates for batch classification
        const candidateSummaries = uncached.slice(0, 30).map((c, i) => ({
            index: i,
            id: c.candidate_id,
            title: c.current_role || 'Unknown',
            experience: (c.experience || '').slice(0, 150)
        }));

        const prompt = `Classify these job candidates into standardized categories.

Candidates:
${JSON.stringify(candidateSummaries, null, 2)}

Return ONLY a valid JSON array (no markdown, no explanation):
[
  {
    "id": "candidate_id",
    "function": "product" | "engineering" | "data" | "design" | "sales" | "marketing" | "hr" | "finance" | "operations" | "general",
    "level": "intern" | "junior" | "mid" | "senior" | "staff" | "principal" | "manager" | "director" | "vp" | "c-level",
    "domain": ["industry1"],
    "confidence": 0.0 to 1.0
  }
]

Important classification rules:
- Product Manager, PM, CPO, VP Product = function: "product"
- Software Engineer, Developer, CTO = function: "engineering"
- Data Scientist, Data Analyst = function: "data"
- Titles without clear function keywords = function: "general"
- Portuguese: "Gerente de Produto" = product, "Engenheiro" = engineering`;

        try {
            const result = await geminiModel.generateContent(prompt);
            const text = result.response.candidates?.[0]?.content?.parts?.[0]?.text || '';

            // Extract JSON array from response
            const jsonMatch = text.match(/\[[\s\S]*\]/);
            if (!jsonMatch) {
                console.error('[JobClassification] Failed to parse batch response:', text.slice(0, 200));
                // Fall back to default for all uncached
                for (const c of uncached) {
                    results.set(c.candidate_id, this.getDefaultClassification());
                }
                return results;
            }

            const classifications = JSON.parse(jsonMatch[0]) as Array<CandidateClassification & { id: string }>;

            for (const cls of classifications) {
                const cacheKey = `candidate:${cls.id}`;
                const classification: JobClassification = {
                    function: cls.function,
                    level: cls.level,
                    domain: cls.domain,
                    confidence: cls.confidence
                };
                this.cache.set(cacheKey, classification);
                results.set(cls.id, classification);
            }

            console.log(`[JobClassification] Batch classified ${classifications.length} candidates`);
        } catch (error: any) {
            console.error('[JobClassification] Batch error:', error.message);
            for (const c of uncached) {
                results.set(c.candidate_id, this.getDefaultClassification());
            }
        }

        return results;
    }

    /**
     * Calculate match score between target job and candidate classification
     * Returns 0-100
     */
    calculateMatchScore(target: JobClassification, candidate: JobClassification): number {
        let score = 0;
        let maxScore = 0;

        // Function match: 40% weight
        maxScore += 40;
        if (target.function === candidate.function) {
            score += 40;
        } else if (target.function === 'general' || candidate.function === 'general') {
            score += 20; // Partial credit for general
        } else if (SIMILAR_FUNCTIONS[target.function]?.includes(candidate.function)) {
            score += 20; // Partial credit for related functions
        }
        // Different function = 0 points

        // Level match: 35% weight
        maxScore += 35;
        const targetLevel = LEVEL_ORDER[target.level] || 4;
        const candidateLevel = LEVEL_ORDER[candidate.level] || 4;
        const levelDistance = Math.abs(targetLevel - candidateLevel);

        if (levelDistance === 0) {
            score += 35;
        } else if (levelDistance === 1) {
            score += 28;
        } else if (levelDistance === 2) {
            score += 18;
        } else {
            score += Math.max(0, 35 - levelDistance * 8);
        }

        // Domain overlap: 25% weight
        maxScore += 25;
        if (target.domain.length > 0 && candidate.domain.length > 0) {
            const overlap = target.domain.filter(d =>
                candidate.domain.some(cd =>
                    cd.toLowerCase().includes(d.toLowerCase()) ||
                    d.toLowerCase().includes(cd.toLowerCase())
                )
            ).length;
            score += Math.min(25, (overlap / target.domain.length) * 25);
        } else {
            score += 12; // Neutral if no domain info
        }

        return Math.round((score / maxScore) * 100);
    }

    /**
     * Get level numeric value for distance calculation
     */
    getLevelValue(level: JobLevel): number {
        return LEVEL_ORDER[level] || 4;
    }

    private getDefaultClassification(): JobClassification {
        return {
            function: 'general',
            level: 'mid',
            domain: [],
            confidence: 0.5
        };
    }
}

// Singleton instance
let instance: JobClassificationService | null = null;

export function getJobClassificationService(): JobClassificationService {
    if (!instance) {
        instance = new JobClassificationService();
    }
    return instance;
}
