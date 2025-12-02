import { GoogleGenerativeAI, GenerativeModel } from '@google/generative-ai';
import * as admin from 'firebase-admin';

export interface SearchStrategy {
    target_role: string;
    seniority: 'entry' | 'mid' | 'senior' | 'executive';
    key_requirements: string[];
    context: string[];
    search_query: string;
    filters: {
        min_years_experience?: number;
        locations?: string[];
    };
    reasoning: string;
}

export class SearchAgent {
    private genAI: GoogleGenerativeAI;
    private model: GenerativeModel;

    constructor() {
        const apiKey = process.env.GOOGLE_API_KEY;
        if (!apiKey) {
            console.warn('GOOGLE_API_KEY is not set. SearchAgent may fail.');
        }
        this.genAI = new GoogleGenerativeAI(apiKey || '');
        this.model = this.genAI.getGenerativeModel({
            model: 'gemini-2.5-flash',
            generationConfig: {
                temperature: 0.2,
                maxOutputTokens: 2048,
                responseMimeType: 'application/json'
            }
        });
    }

    async analyzeQuery(userQuery: string): Promise<SearchStrategy> {
        try {
            const prompt = this.buildPrompt(userQuery);
            const result = await this.model.generateContent(prompt);
            const response = result.response;
            const text = response.candidates?.[0]?.content?.parts?.[0]?.text;

            if (!text) {
                throw new Error('Empty response from Search Agent');
            }

            // Parse JSON response
            let strategy: SearchStrategy;
            try {
                const jsonStr = text.replace(/```json\n?|\n?```/g, '').trim();
                strategy = JSON.parse(jsonStr);
            } catch (e) {
                console.error('Failed to parse Agent response:', text);
                throw new Error('Invalid JSON response from Search Agent');
            }

            return strategy;
        } catch (error) {
            console.error('Error in Search Agent:', error);
            // Fallback strategy if Agent fails
            return {
                target_role: userQuery,
                seniority: 'mid',
                key_requirements: [],
                context: [],
                search_query: userQuery,
                filters: {},
                reasoning: 'Agent failed, falling back to raw query.'
            };
        }
    }

    private buildPrompt(query: string): string {
        return `You are an expert Senior Technical Recruiter and Search Strategist.
Your goal is to translate a recruiter's raw request into a precise, structured search strategy for a vector database.

USER REQUEST: "${query}"

YOUR TASK:
1. Analyze the request to understand the *intent*, *seniority*, and *context*.
2. Extract specific technical and soft skill requirements.
3. Identify implicit filters (e.g., "seasoned" -> 10+ years experience).
4. Formulate an optimized "search_query" that captures the semantic essence (role + context) for vector retrieval.

OUTPUT SCHEMA (JSON):
{
  "target_role": "Standardized job title (e.g. 'Chief Technology Officer')",
  "seniority": "One of: 'entry', 'mid', 'senior', 'executive'",
  "key_requirements": ["List of top 3-5 must-have skills/technologies"],
  "context": ["List of context keywords (e.g. 'Startup', 'Fintech', 'Turnaround', 'B2B')"],
  "search_query": "A rich, descriptive sentence optimized for vector embedding. Include role, key skills, and context.",
  "filters": {
    "min_years_experience": Number (estimate based on seniority/request, e.g. 15 for CTO),
    "locations": ["List of locations if specified"]
  },
  "reasoning": "Brief explanation of why you chose this strategy."
}

EXAMPLES:
Input: "Need a CTO who has done a Series B turnaround"
Output: {
  "target_role": "Chief Technology Officer",
  "seniority": "executive",
  "key_requirements": ["Leadership", "Strategic Planning", "Crisis Management", "Scaling"],
  "context": ["Series B", "Turnaround", "Growth Phase", "Startup"],
  "search_query": "Chief Technology Officer (CTO) with experience in Series B startups, turnaround strategies, and scaling engineering teams.",
  "filters": { "min_years_experience": 12 },
  "reasoning": "User specified 'CTO' (Executive) and 'Series B turnaround', implying deep leadership and crisis management experience."
}

Input: "Java dev for a bank, junior level"
Output: {
  "target_role": "Java Developer",
  "seniority": "entry",
  "key_requirements": ["Java", "Spring Boot", "SQL"],
  "context": ["Banking", "Fintech", "Enterprise"],
  "search_query": "Junior Java Developer with experience in banking or fintech sectors.",
  "filters": { "min_years_experience": 0 },
  "reasoning": "Explicitly asked for 'junior' and 'bank'."
}
`;
    }
}

import * as functions from 'firebase-functions';

const agent = new SearchAgent();

export const analyzeSearchQuery = functions.https.onCall(async (request) => {
    if (!request.data.query) {
        throw new functions.https.HttpsError('invalid-argument', 'The function must be called with a "query" argument.');
    }

    try {
        const strategy = await agent.analyzeQuery(request.data.query);
        return strategy;
    } catch (error) {
        console.error('Error analyzing search query:', error);
        throw new functions.https.HttpsError('internal', 'Failed to analyze search query.');
    }
});
