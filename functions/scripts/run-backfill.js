/**
 * Direct backfill script that runs locally and calls Gemini + Firestore
 * This avoids needing to call the cloud function with auth
 */

const admin = require('firebase-admin');
const { GoogleGenerativeAI } = require('@google/generative-ai');
require('dotenv').config();

// Initialize Firebase Admin with default credentials
admin.initializeApp({
    credential: admin.credential.applicationDefault(),
    projectId: 'headhunter-ai-0088'
});

const db = admin.firestore();
const genAI = new GoogleGenerativeAI(process.env.GOOGLE_API_KEY);

const VALID_FUNCTIONS = [
    'engineering', 'product', 'design', 'data',
    'sales', 'marketing', 'hr', 'finance', 'operations', 'general'
];

const VALID_LEVELS = [
    'c-level', 'vp', 'director', 'manager', 'senior', 'mid', 'junior', 'intern'
];

async function classifyCandidate(profile) {
    const model = genAI.getGenerativeModel({
        model: 'gemini-2.5-flash-lite',
        generationConfig: { temperature: 0.1, maxOutputTokens: 1024 }
    });

    // Build profile text with ALL available data
    const profileParts = [];

    // Job titles are the BEST signal for specialty
    if (profile.title_keywords?.length) {
        profileParts.push(`Job Titles: ${profile.title_keywords.join(', ')}`);
    }
    if (profile.current_role) {
        profileParts.push(`Current Role: ${profile.current_role}`);
    }
    if (profile.skills?.length) {
        profileParts.push(`Skills: ${profile.skills.slice(0, 20).join(', ')}`);
    }
    if (profile.summary) {
        profileParts.push(`Summary: ${profile.summary.slice(0, 300)}`);
    }
    if (profile.companies?.length) {
        profileParts.push(`Companies: ${profile.companies.slice(0, 5).join(', ')}`);
    }

    const profileText = profileParts.join('\n');

    const prompt = `Classify this candidate's career functions. Analyze job titles carefully for specialties.

SPECIALTY DETECTION FROM JOB TITLES:
- "Frontend Developer", "React Developer", "UI Engineer" → engineering with specialty: ["frontend"]
- "Backend Developer", "API Engineer", "Server-side" → engineering with specialty: ["backend"]  
- "Full Stack", "Fullstack" → engineering with specialty: ["fullstack"]
- "Mobile Developer", "iOS", "Android" → engineering with specialty: ["mobile"]
- "DevOps", "SRE", "Platform" → engineering with specialty: ["devops"]
- "QA", "Test", "SDET" → engineering with specialty: ["qa"]
- "UX Designer", "UI Designer", "Product Designer" → design with appropriate specialties

PROFILE:
${profileText || 'No profile data available'}

Return JSON with confidence scores 0.0-1.0:
{"functions": [{"name": "engineering", "confidence": 0.9, "level": "senior", "specialties": ["frontend"]}]}

Valid functions: ${VALID_FUNCTIONS.join(', ')}
Valid levels: ${VALID_LEVELS.join(', ')}`;

    try {
        const result = await model.generateContent(prompt);
        const text = result.response.text();
        const jsonMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/) || [null, text];
        const parsed = JSON.parse(jsonMatch[1].trim());

        if (!parsed.functions?.length) throw new Error('No functions');

        let functions = parsed.functions
            .filter(f => f.name && typeof f.confidence === 'number')
            .map(f => ({
                name: VALID_FUNCTIONS.includes(f.name) ? f.name : 'general',
                confidence: Math.max(0, Math.min(1, f.confidence)),
                level: VALID_LEVELS.includes(f.level) ? f.level : 'mid',
                specialties: Array.isArray(f.specialties) ? f.specialties : []
            }))
            .sort((a, b) => b.confidence - a.confidence);

        // ===================================================================
        // SPECIALTY HEURISTIC: Default to backend for generic engineering titles
        // 
        // Pattern observed: Frontend developers specify "Frontend" in titles,
        // Backend developers often just say "Software Engineer" or "Staff Engineer"
        // ===================================================================
        const allTitles = (profile.title_keywords || []).join(' ').toLowerCase();
        const frontendSignals = ['frontend', 'front-end', 'front end', 'react', 'vue', 'angular',
            'ui engineer', 'ui developer', 'css', 'web developer'];
        const backendSignals = ['backend', 'back-end', 'back end', 'api', 'server', 'platform',
            'infrastructure', 'devops', 'sre', 'database', 'python', 'java', 'golang', 'ruby'];

        const hasFrontendSignal = frontendSignals.some(s => allTitles.includes(s));
        const hasBackendSignal = backendSignals.some(s => allTitles.includes(s));

        // Apply heuristic to engineering functions with empty specialties
        functions = functions.map(f => {
            if (f.name === 'engineering' && (!f.specialties || f.specialties.length === 0)) {
                if (hasFrontendSignal && !hasBackendSignal) {
                    // Explicit frontend signal
                    f.specialties = ['frontend'];
                } else if (hasBackendSignal && !hasFrontendSignal) {
                    // Explicit backend signal
                    f.specialties = ['backend'];
                } else if (!hasFrontendSignal && !hasBackendSignal) {
                    // Generic title like "Software Engineer", "Staff Engineer" → default backend
                    // Rationale: Frontend devs tend to specify "Frontend", backend is the default
                    f.specialties = ['backend'];
                } else {
                    // Has both signals → fullstack
                    f.specialties = ['fullstack'];
                }
            }
            return f;
        });

        return {
            functions,
            primary_function: functions[0].name,
            primary_level: functions[0].level,
            classification_version: '2.0',
            classified_at: new Date().toISOString(),
            model_used: 'gemini-2.5-flash-lite'
        };
    } catch (error) {
        console.error('Classification error:', error.message);
        return {
            functions: [{ name: 'general', confidence: 0.5, level: 'mid', specialties: [] }],
            primary_function: 'general',
            primary_level: 'mid',
            classification_version: '2.0',
            classified_at: new Date().toISOString(),
            model_used: 'fallback'
        };
    }
}

async function runBackfill(batchSize = 50, startAfterDoc = null, maxBatches = 10) {
    let startAfter = startAfterDoc;
    let totalProcessed = 0;
    let totalSuccess = 0;
    let totalErrors = 0;
    let batchNumber = 0;

    console.log('=== LLM Classification Backfill ===');
    console.log(`Model: gemini-2.5-flash-lite (cost: ~$4 for 29K)`);
    console.log(`Batch size: ${batchSize}`);
    console.log(`Max batches: ${maxBatches}`);
    console.log('');

    while (batchNumber < maxBatches) {
        batchNumber++;
        console.log(`\n--- Batch ${batchNumber} ---`);

        let query = db.collection('candidates')
            .orderBy('__name__')
            .limit(batchSize);

        if (startAfter) {
            const startDoc = await db.collection('candidates').doc(startAfter).get();
            if (startDoc.exists) {
                query = query.startAfter(startDoc);
            }
        }

        const snapshot = await query.get();

        if (snapshot.empty) {
            console.log('No more candidates.');
            break;
        }

        for (const doc of snapshot.docs) {
            const data = doc.data();

            // Process candidates that need classification
            // Either: newly imported (needs_classification=true) OR engineering without proper specialty
            const existingFunctions = data.searchable?.functions || [];
            const engineeringFuncs = existingFunctions.filter(f => f.name === 'engineering');
            const hasProperSpecialty = engineeringFuncs.some(f =>
                f.specialties?.some(s => ['backend', 'frontend', 'fullstack', 'mobile', 'devops'].includes(s))
            );
            const needsClassification = data.processing?.needs_classification === true;

            // Skip if already properly classified
            if (data.searchable?.classification_version === '2.0' && hasProperSpecialty && !needsClassification) {
                totalProcessed++;
                continue;
            }

            const profile = {
                name: data.profile?.name || data.name || 'Unknown',
                current_role: data.profile?.current_role || '',
                title_keywords: data.searchable?.title_keywords || [],  // Job titles like 'Senior Frontend Developer'
                skills: data.profile?.skills || data.profile?.top_skills?.map(s => s.skill || s) || [],
                summary: data.profile?.summary || '',
                companies: data.searchable?.companies || []  // Company history
            };

            try {
                const classification = await classifyCandidate(profile);

                await doc.ref.update({
                    'searchable.functions': classification.functions,
                    'searchable.function': classification.primary_function,
                    'searchable.level': classification.primary_level,
                    'searchable.classification_version': classification.classification_version,
                    'searchable.classified_at': classification.classified_at,
                    'searchable.classification_model': classification.model_used,
                });

                console.log(`✓ ${profile.name}: ${classification.primary_function}/${classification.primary_level}`);
                totalSuccess++;
            } catch (error) {
                console.error(`✗ ${doc.id}: ${error.message}`);
                totalErrors++;
            }

            totalProcessed++;

            // Rate limit: 50ms between calls
            await new Promise(r => setTimeout(r, 50));
        }

        startAfter = snapshot.docs[snapshot.docs.length - 1].id;
        console.log(`Batch ${batchNumber} done. Total: ${totalProcessed}, Success: ${totalSuccess}, Errors: ${totalErrors}`);
        console.log(`Continue from: ${startAfter}`);

        if (snapshot.size < batchSize) {
            console.log('\nReached end of candidates.');
            break;
        }
    }

    console.log('\n=== Backfill Summary ===');
    console.log(`Total processed: ${totalProcessed}`);
    console.log(`Successful: ${totalSuccess}`);
    console.log(`Errors: ${totalErrors}`);
    console.log(`Last ID: ${startAfter}`);

    return { totalProcessed, totalSuccess, totalErrors, lastId: startAfter };
}

// Classify new imports (1087 candidates ÷ 50 per batch = ~25 batches)
runBackfill(50, null, 30).then(result => {
    console.log('\nResult:', JSON.stringify(result, null, 2));
    process.exit(0);
}).catch(err => {
    console.error('Fatal:', err);
    process.exit(1);
});
