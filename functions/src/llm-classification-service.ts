/**
 * LLM-Based Multi-Function Classification Service
 * 
 * Uses Gemini to classify candidates into multiple career functions
 * with confidence scores, support for specialties, and different levels per function.
 * 
 * This replaces the brittle rule-based classification system.
 */

import { GoogleGenerativeAI } from '@google/generative-ai';

// Types for multi-function classification
export interface FunctionClassification {
    name: string;           // engineering, product, design, data, sales, marketing, hr, finance, operations
    confidence: number;     // 0.0 to 1.0
    level: string;          // c-level, vp, director, manager, senior, mid, junior
    specialties?: string[]; // e.g., ["frontend", "react"] for engineering, ["ux", "ui"] for design
}

export interface CandidateClassification {
    functions: FunctionClassification[];
    primary_function: string;       // Highest confidence function
    primary_level: string;          // Level for primary function
    classification_version: string; // For tracking schema changes
    classified_at: string;          // ISO timestamp
    model_used: string;             // Which model was used
}

// Valid functions
const VALID_FUNCTIONS = [
    'engineering', 'product', 'design', 'data',
    'sales', 'marketing', 'hr', 'finance', 'operations', 'general'
];

// Valid levels
const VALID_LEVELS = [
    'c-level', 'vp', 'director', 'manager', 'senior', 'mid', 'junior', 'intern'
];

export class LLMClassificationService {
    private genAI: GoogleGenerativeAI;
    private modelName: string = 'gemini-2.5-flash-lite';  // Cost-effective for classification

    constructor() {
        const apiKey = process.env.GOOGLE_API_KEY || '';
        this.genAI = new GoogleGenerativeAI(apiKey);
    }

    /**
     * Classify a candidate based on their resume/profile data
     */
    async classifyCandidate(candidateData: {
        name?: string;
        current_role?: string;
        experience?: any[];
        skills?: string[];
        summary?: string;
    }): Promise<CandidateClassification> {
        const startTime = Date.now();

        try {
            const model = this.genAI.getGenerativeModel({
                model: this.modelName,
                generationConfig: {
                    temperature: 0.1,  // Low temperature for consistent classification
                    maxOutputTokens: 2048,
                }
            });

            const profileText = this.formatProfileForClassification(candidateData);
            const prompt = this.buildClassificationPrompt(profileText);

            const result = await model.generateContent(prompt);
            const responseText = result.response.text();

            const classification = this.parseClassificationResponse(responseText);

            const latency = Date.now() - startTime;
            console.log(`[LLMClassification] Classified ${candidateData.name || 'unknown'} in ${latency}ms: primary=${classification.primary_function}/${classification.primary_level}`);

            return classification;

        } catch (error: any) {
            console.error('[LLMClassification] Error:', error.message);
            // Return a safe default classification
            return this.getDefaultClassification();
        }
    }

    /**
     * Format candidate profile data for the LLM prompt
     */
    private formatProfileForClassification(data: any): string {
        const parts: string[] = [];

        if (data.current_role) {
            parts.push(`Current Role: ${data.current_role}`);
        }

        if (data.summary) {
            parts.push(`Summary: ${data.summary.slice(0, 500)}`);
        }

        if (data.skills && data.skills.length > 0) {
            const skills = Array.isArray(data.skills)
                ? data.skills.slice(0, 20).join(', ')
                : data.skills;
            parts.push(`Skills: ${skills}`);
        }

        if (data.experience && data.experience.length > 0) {
            const recentRoles = data.experience.slice(0, 5).map((exp: any) => {
                const role = exp.role || exp.title || '';
                const company = exp.company || '';
                return `${role} at ${company}`;
            }).filter((r: string) => r.length > 5).join('; ');

            if (recentRoles) {
                parts.push(`Career History: ${recentRoles}`);
            }
        }

        return parts.join('\n');
    }

    /**
     * Build the classification prompt for Gemini
     */
    private buildClassificationPrompt(profileText: string): string {
        return `You are an expert career analyst and recruiter. Analyze this candidate's profile and classify their career functions.

IMPORTANT: A person can have MULTIPLE functions. Many professionals span multiple areas:
- Full Stack Developer = engineering (frontend + backend)
- CTO/CPO = engineering + product  
- UX/UI Designer = design (ux + ui + visual)
- Data Scientist who codes = data + engineering
- Product Designer = design + product
- DevOps Engineer = engineering + operations
- Growth Marketer = marketing + data

PROFILE:
${profileText}

AVAILABLE FUNCTIONS (include ALL that apply with confidence 0.0-1.0):
- engineering: Software development, infrastructure, devops, QA, architecture
- product: Product management, product strategy, product ownership
- design: UX design, UI design, visual design, product design, graphic design
- data: Data science, analytics, ML engineering, data engineering, BI
- sales: Account executive, sales, business development, partnerships
- marketing: Growth, brand, content, performance marketing, SEO
- hr: People operations, recruiting, talent acquisition, HR business partner
- finance: Accounting, FP&A, controller, treasury, investor relations
- operations: Operations, supply chain, logistics, customer success
- general: General management, consulting, or cannot determine

LEVELS (assign for each function):
- c-level: CEO, CTO, CPO, CFO, COO, CMO, Chief Officer, President, Founder
- vp: Vice President, SVP, EVP
- director: Director, Senior Director, Head of
- manager: Manager, Senior Manager, Team Lead, Tech Lead
- senior: Senior individual contributor, Staff, Principal
- mid: Mid-level individual contributor, regular IC
- junior: Junior, Associate, Entry-level
- intern: Intern, Trainee

SPECIALTIES (optional, for nuance):
- For engineering: frontend, backend, fullstack, mobile, devops, infra, qa, security
- For design: ux, ui, visual, product, graphic, motion, brand
- For data: analytics, science, engineering, ml, bi

Return JSON in this exact format:
\`\`\`json
{
  "functions": [
    {"name": "engineering", "confidence": 0.9, "level": "senior", "specialties": ["frontend", "react"]},
    {"name": "design", "confidence": 0.4, "level": "mid", "specialties": ["ui"]}
  ]
}
\`\`\`

Rules:
1. Include ALL applicable functions with confidence > 0.2
2. Order by confidence (highest first)
3. Be generous - if there's any signal for a function, include it
4. Specialties are optional but helpful for nuance
5. Level should reflect their seniority IN THAT FUNCTION`;
    }

    /**
     * Parse the LLM response into structured classification
     */
    private parseClassificationResponse(responseText: string): CandidateClassification {
        try {
            // Extract JSON from response (handle markdown code blocks)
            let jsonStr = responseText;
            const jsonMatch = responseText.match(/```(?:json)?\s*([\s\S]*?)```/);
            if (jsonMatch) {
                jsonStr = jsonMatch[1];
            }

            const parsed = JSON.parse(jsonStr.trim());

            if (!parsed.functions || !Array.isArray(parsed.functions)) {
                throw new Error('Invalid response format - missing functions array');
            }

            // Validate and normalize functions
            const functions: FunctionClassification[] = parsed.functions
                .filter((f: any) => f.name && typeof f.confidence === 'number')
                .map((f: any) => ({
                    name: VALID_FUNCTIONS.includes(f.name) ? f.name : 'general',
                    confidence: Math.max(0, Math.min(1, f.confidence)),
                    level: VALID_LEVELS.includes(f.level) ? f.level : 'mid',
                    specialties: Array.isArray(f.specialties) ? f.specialties : []
                }))
                .sort((a: FunctionClassification, b: FunctionClassification) => b.confidence - a.confidence);

            // Ensure at least one function
            if (functions.length === 0) {
                return this.getDefaultClassification();
            }

            return {
                functions,
                primary_function: functions[0].name,
                primary_level: functions[0].level,
                classification_version: '2.0',
                classified_at: new Date().toISOString(),
                model_used: this.modelName
            };

        } catch (error: any) {
            console.error('[LLMClassification] Parse error:', error.message);
            console.error('[LLMClassification] Raw response:', responseText.substring(0, 500));
            return this.getDefaultClassification();
        }
    }

    /**
     * Return a safe default classification
     */
    private getDefaultClassification(): CandidateClassification {
        return {
            functions: [
                { name: 'general', confidence: 0.5, level: 'mid', specialties: [] }
            ],
            primary_function: 'general',
            primary_level: 'mid',
            classification_version: '2.0',
            classified_at: new Date().toISOString(),
            model_used: 'fallback'
        };
    }

    /**
     * Convert multi-function classification to legacy single-function format
     * for backward compatibility
     */
    static toLegacyFormat(classification: CandidateClassification): {
        function: string;
        level: string;
    } {
        return {
            function: classification.primary_function,
            level: classification.primary_level
        };
    }

    /**
     * Check if a candidate matches a target function at or above a confidence threshold
     */
    static matchesFunction(
        classification: CandidateClassification,
        targetFunction: string,
        minConfidence: number = 0.3
    ): { matches: boolean; confidence: number; level: string } {
        const match = classification.functions.find(f => f.name === targetFunction);

        if (!match || match.confidence < minConfidence) {
            return { matches: false, confidence: 0, level: 'mid' };
        }

        return {
            matches: true,
            confidence: match.confidence,
            level: match.level
        };
    }
}

// Singleton instance
let classificationServiceInstance: LLMClassificationService | null = null;

export function getLLMClassificationService(): LLMClassificationService {
    if (!classificationServiceInstance) {
        classificationServiceInstance = new LLMClassificationService();
    }
    return classificationServiceInstance;
}
