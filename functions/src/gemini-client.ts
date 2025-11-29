import { VertexAI } from '@google-cloud/vertexai';

const project = process.env.GOOGLE_CLOUD_PROJECT || 'headhunter-ai-0088';
const location = 'us-central1';

const vertex_ai = new VertexAI({ project: project, location: location });

// Instantiate the model
// Using gemini-1.5-pro for high quality reasoning
export const geminiModel = vertex_ai.getGenerativeModel({
    model: 'gemini-1.5-pro'
});
