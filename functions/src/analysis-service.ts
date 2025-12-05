import { GoogleGenerativeAI, GenerativeModel } from '@google/generative-ai';
import * as admin from 'firebase-admin';
import { GEMINI_MODEL, GEMINI_VISION_MODEL, getGeminiConfig } from './ai-models';

export class AnalysisService {
  private genAI: GoogleGenerativeAI;
  private model: GenerativeModel;

  constructor() {
    const apiKey = process.env.GOOGLE_API_KEY;
    if (!apiKey) {
      console.warn('GOOGLE_API_KEY is not set. AnalysisService may fail.');
    }
    this.genAI = new GoogleGenerativeAI(apiKey || '');
    this.model = this.genAI.getGenerativeModel({
      ...getGeminiConfig({ responseMimeType: 'application/json' }),
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
    } catch (error: any) {
      console.error('Error analyzing candidate:', error);
      if (error.response) {
        console.error('Error response:', JSON.stringify(error.response, null, 2));
      }
      throw error;
    }
  }

  /**
   * Extract text from a file using Gemini
   */
  async extractText(fileBuffer: Buffer, mimeType: string): Promise<string> {
    try {
      const model = this.genAI.getGenerativeModel({ model: GEMINI_VISION_MODEL });
      const prompt = "Extract all text from this document. Return ONLY the text, no markdown formatting or comments.";

      const imageParts = [
        {
          inlineData: {
            data: fileBuffer.toString('base64'),
            mimeType: mimeType
          }
        }
      ];

      const result = await model.generateContent([prompt, ...imageParts]);
      const response = result.response;
      return response.text() || "";
    } catch (error) {
      console.error('Error extracting text with Gemini:', error);
      throw error;
    }
  }

  private buildAnalysisPrompt(candidate: any): string {
    const name = candidate.name || "Unknown";
    const experience = candidate.experience || "";
    const education = candidate.education || "";
    const email = candidate.email || "";
    const companies = candidate.companies || [];

    return `You are a Senior Executive Recruiter with 20+ years of experience in high-growth tech companies.
Your expertise lies in identifying top-tier talent, understanding complex engineering career paths, and filtering out noise.

CANDIDATE PROFILE:
Name: ${name}
Email: ${email}
Companies: ${companies.join(', ')}

EXPERIENCE:
${experience}

EDUCATION:
${education}

YOUR TASK:
Perform a deep, critical analysis of this candidate. Do not just summarize; EVALUATE.
Separate EXPLICIT skills from INFERRED skills based on the company's engineering culture and the role's complexity.

CRITICAL INSTRUCTIONS FOR EDUCATION:
1.  **FILTER STRICTLY**: Only include formal Undergraduate (Bachelor's) and Graduate (Master's, PhD, MBA, JD) degrees.
2.  **IGNORE**: Short courses, bootcamps, certifications, "nanodegrees", and non-degree programs.
3.  **VALIDATE**: If the education section lists a university but no degree (e.g., "Coursework in CS"), do NOT list it as a degree.

CRITICAL INSTRUCTIONS FOR ANALYSIS:
1.  **Company Tiering**: Recognize the caliber of companies (e.g., FAANG, high-growth startups, consultancies) and use this to infer skill depth.
2.  **Career Velocity**: Analyze the speed of promotion and tenure. Is this a job hopper or a pillar?
3.  **Role Scope**: Distinguish between "participant" and "owner". Did they build it, or just maintain it?

OUTPUT SCHEMA (JSON ONLY):
{
  "explicit_skills": {
    "technical_skills": [{"skill": "...", "confidence": 100, "evidence": ["mentioned in experience"]}],
    "tools_technologies": [{"skill": "...", "confidence": 100}],
    "soft_skills": [{"skill": "...", "confidence": 100}]
  },
  "inferred_skills": {
    "highly_probable_skills": [{"skill": "...", "confidence": 95, "reasoning": "Inferred from [Company] [Role] stack", "skill_category": "technical"}],
    "probable_skills": [{"skill": "...", "confidence": 80}]
  },
  "education_analysis": {
    "degrees": [{"degree": "...", "institution": "...", "year": "...", "level": "Undergrad/Grad"}],
    "notes": "Brief comment on education quality/relevance"
  },
  "career_trajectory_analysis": {
    "current_level": "...", "years_experience": 0, "promotion_velocity": "Fast/Average/Slow", "career_progression": "..."
  },
  "recruiter_insights": {
    "overall_rating": "Top 1% / Top 10% / Strong / Average / Weak",
    "recommendation": "Strong Hire / Hire / Interview / Pass",
    "one_line_pitch": "The 'sell' for this candidate",
    "red_flags": ["List any concerns"]
  },
  "personal_details": {
    "linkedin": "Extract LinkedIn URL if present",
    "github": "Extract GitHub URL if present",
    "name": "Extract Name if present",
    "email": "Extract Email if present",
    "location": "Inferred location"
  }
}
`;
  }
}
