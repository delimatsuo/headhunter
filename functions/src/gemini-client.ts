import { VertexAI } from '@google-cloud/vertexai';
import { GEMINI_MODEL } from './ai-models';

const project = process.env.GOOGLE_CLOUD_PROJECT || 'headhunter-ai-0088';
const location = 'us-central1';

const vertex_ai = new VertexAI({ project: project, location: location });

// Instantiate the model - uses centralized config from ai-models.ts
export const geminiModel = vertex_ai.getGenerativeModel({
    model: GEMINI_MODEL
});

// High-reasoning model for reranking
export const geminiReasoningModel = vertex_ai.getGenerativeModel({
    model: 'gemini-2.5-pro' // Explicitly use Pro for reasoning tasks
});
