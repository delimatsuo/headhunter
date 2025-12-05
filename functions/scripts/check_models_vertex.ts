import { VertexAI } from '@google-cloud/vertexai';
import * as dotenv from 'dotenv';
import { resolve } from 'path';

dotenv.config({ path: resolve(__dirname, '../../.env') });

async function main() {
    const project = process.env.GOOGLE_CLOUD_PROJECT || 'headhunter-ai-0088';
    const location = 'us-central1';

    console.log(`Checking models for project: ${project} in ${location}`);

    const vertexAI = new VertexAI({ project, location });
    const model = vertexAI.getGenerativeModel({ model: 'gemini-2.5-flash-001' });

    try {
        console.log('Attempting to generate content with gemini-1.5-flash-001...');
        const result = await model.generateContent('Hello');
        console.log('Success! Model is accessible.');
        console.log(result.response.candidates?.[0]?.content?.parts?.[0]?.text);
    } catch (error: any) {
        console.error('Error accessing model:', error.message);
        if (error.message.includes('404')) {
            console.log('Model not found. Trying gemini-pro...');
            const modelPro = vertexAI.getGenerativeModel({ model: 'gemini-pro' });
            try {
                const resultPro = await modelPro.generateContent('Hello');
                console.log('Success with gemini-pro!');
            } catch (e: any) {
                console.error('Error with gemini-pro:', e.message);
            }
        }
    }
}

main().catch(console.error);
