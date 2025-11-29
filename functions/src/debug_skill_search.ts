
import * as admin from 'firebase-admin';
import { VectorSearchService } from './vector-search';

// Initialize Firebase Admin
const projectId = 'headhunter-ai-0088';
if (!admin.apps.length) {
    admin.initializeApp({
        credential: admin.credential.applicationDefault(),
        projectId: projectId,
    });
}

async function debugSearch() {
    console.log('Starting debug search...');

    try {
        const vectorService = new VectorSearchService();

        // Test embedding generation first
        console.log('Testing embedding generation...');
        try {
            const embedding = await vectorService.generateEmbedding('test query');
            console.log('Embedding generation successful, length:', embedding.length);
        } catch (error) {
            console.error('Embedding generation failed:', error);
            return;
        }

        // Test skill-aware search
        console.log('Testing skill-aware search...');
        const query = {
            text_query: "Senior Software Engineer with React and Node.js",
            required_skills: [
                { skill: "React", minimum_confidence: 70, weight: 1.0, category: "technical" }
            ],
            limit: 5
        };

        const results = await vectorService.searchCandidatesSkillAware(query);
        console.log(`Search returned ${results.length} results`);

        if (results.length > 0) {
            console.log('First result:', JSON.stringify(results[0], null, 2));
        }

    } catch (error) {
        console.error('Debug search failed:', error);
        if (error instanceof Error) {
            console.error('Stack:', error.stack);
        }
    }
}

debugSearch().catch(console.error);
