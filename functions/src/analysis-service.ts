import { VertexAI, GenerativeModel } from '@google-cloud/vertexai';
import * as admin from 'firebase-admin';

export class AnalysisService {
    private vertexAI: VertexAI;
    private model: GenerativeModel;

    constructor() {
        this.vertexAI = new VertexAI({
            project: process.env.GOOGLE_CLOUD_PROJECT || 'headhunter-ai-0088',
            location: 'us-central1'
        });
        this.model = this.vertexAI.getGenerativeModel({
            model: 'gemini-1.5-flash',
            generationConfig: {
                temperature: 0.2,
                maxOutputTokens: 8192,
                responseMimeType: 'application/json'
            }
        });
    }

    /**
     * Analyze a candidate profile using Gemini
     */
    async analyzeCandidate(candidateData: any): Promise<any> {
        try {
            const prompt = this.buildAnalysisPrompt(candidateData);

            const result = await this.model.generateContent(prompt);
            const response = result.response;
            const text = response.candidates?.[0]?.content?.parts?.[0]?.text;

            if (!text) {
                throw new Error('Empty response from Gemini');
            }

            // Parse JSON response
            let analysis: any;
            try {
                // Clean up markdown code blocks if present
                const jsonStr = text.replace(/```json\n?|\n?```/g, '').trim();
                analysis = JSON.parse(jsonStr);
            } catch (e) {
                console.error('Failed to parse Gemini response:', text);
                throw new Error('Invalid JSON response from Gemini');
            }

            return analysis;
        } catch (error) {
            console.error('Error analyzing candidate:', error);
            throw error;
        }
    }

    private buildAnalysisPrompt(candidate: any): string {
        const name = candidate.name || "Unknown";
        const experience = candidate.experience || "";
        const education = candidate.education || "";

        return `You are a senior tech recruiter with 15+ years of experience.
You have deep knowledge of tech stacks, company engineering cultures, and can infer likely skills based on roles and companies.

CANDIDATE: ${name}

EXPERIENCE:
${experience}

EDUCATION:
${education}

YOUR TASK:
Analyze this candidate like a senior recruiter would. Separate what they EXPLICITLY mention from what you can INFER based on company context, role requirements, and industry knowledge.

Return ONLY valid JSON (no markdown, no code blocks) with these top-level keys:
explicit_skills, inferred_skills, company_context_skills, composite_skill_profile, career_trajectory_analysis, market_positioning, recruiter_insights.

Schema structure:
{
  "explicit_skills": {
    "technical_skills": [{"skill": "...", "confidence": 100, "evidence": ["mentioned in experience"]}],
    "tools_technologies": [{"skill": "...", "confidence": 100}],
    "soft_skills": [{"skill": "...", "confidence": 100}]
  },
  "inferred_skills": {
    "highly_probable_skills": [{"skill": "...", "confidence": 95, "reasoning": "strong indicators", "skill_category": "technical"}],
    "probable_skills": [{"skill": "...", "confidence": 80}]
  },
  "career_trajectory_analysis": {
    "current_level": "...", "years_experience": 0, "promotion_velocity": "...", "career_progression": "..."
  },
  "recruiter_insights": {
    "overall_rating": "...", "recommendation": "...", "one_line_pitch": "..."
  },
  "personal_details": {
    "linkedin": "Extract LinkedIn URL if present in text",
    "github": "Extract GitHub URL if present",
    "email": "Extract Email if present"
  }
}

CRITICAL:
1. Extract the LinkedIn URL if it appears anywhere in the text (comments, experience, etc.).
2. Estimate years of experience accurately.
3. Determine current level (Junior, Mid, Senior, Staff, Executive).
`;
    }
}
