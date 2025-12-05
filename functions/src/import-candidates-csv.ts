/**
 * CSV Import for Candidates
 * Allows admins to bulk import candidates from CSV/Excel data
 */
import { onCall, HttpsError } from 'firebase-functions/v2/https';
import { getFirestore, Timestamp } from 'firebase-admin/firestore';
import { VectorSearchService } from './vector-search';
import * as z from 'zod';

const db = getFirestore();
const vectorService = new VectorSearchService();

// Schema for CSV row data
const CandidateRowSchema = z.object({
    name: z.string().min(1, 'Name is required'),
    email: z.string().email().optional().or(z.literal('')),
    phone: z.string().optional(),
    current_title: z.string().optional(),
    current_company: z.string().optional(),
    location: z.string().optional(),
    linkedin_url: z.string().url().optional().or(z.literal('')),
    skills: z.string().optional(), // Comma-separated
    years_experience: z.number().optional().or(z.string().transform(val => val ? parseInt(val) : undefined)),
    notes: z.string().optional(),
});

const ImportRequestSchema = z.object({
    rows: z.array(z.record(z.string())),
    columnMapping: z.record(z.string()), // Maps CSV columns to our fields
    dedupeStrategy: z.enum(['skip', 'update', 'merge']).default('skip'),
    source: z.string().default('CSV Import'),
});

type CandidateRow = z.infer<typeof CandidateRowSchema>;

interface ImportResult {
    success: boolean;
    totalRows: number;
    imported: number;
    skipped: number;
    errors: Array<{ row: number; error: string }>;
    candidateIds: string[];
}

/**
 * Import candidates from CSV data
 * Requires admin role
 */
export const importCandidatesCSV = onCall(
    {
        memory: '2GiB',
        timeoutSeconds: 540, // 9 minutes for large imports
    },
    async (request): Promise<ImportResult> => {
        // Auth check
        if (!request.auth) {
            throw new HttpsError('unauthenticated', 'Authentication required');
        }

        // Get user's org_id and role
        const userId = request.auth.uid;
        const userDoc = await db.collection('users').doc(userId).get();
        if (!userDoc.exists) {
            throw new HttpsError('permission-denied', 'User not found');
        }

        const userData = userDoc.data()!;
        const orgId = userData.org_id;
        const role = userData.role;

        // Only admins can import
        if (role !== 'admin' && role !== 'super_admin') {
            throw new HttpsError('permission-denied', 'Admin access required for bulk import');
        }

        // Validate input
        let validatedInput;
        try {
            validatedInput = ImportRequestSchema.parse(request.data);
        } catch (error) {
            if (error instanceof z.ZodError) {
                throw new HttpsError('invalid-argument', `Invalid input: ${error.errors.map(e => e.message).join(', ')}`);
            }
            throw error;
        }

        const { rows, columnMapping, dedupeStrategy, source } = validatedInput;

        console.log(`Starting CSV import: ${rows.length} rows, strategy: ${dedupeStrategy}`);

        const result: ImportResult = {
            success: true,
            totalRows: rows.length,
            imported: 0,
            skipped: 0,
            errors: [],
            candidateIds: [],
        };

        // Get existing emails for deduplication
        const existingEmails = new Map<string, string>(); // email -> candidate_id
        if (dedupeStrategy !== 'update') {
            const existingCandidates = await db
                .collection('candidates')
                .where('org_id', '==', orgId)
                .select('email', 'personal.email')
                .get();

            existingCandidates.forEach(doc => {
                const data = doc.data();
                const email = data.email || data.personal?.email;
                if (email) {
                    existingEmails.set(email.toLowerCase(), doc.id);
                }
            });
        }

        // Process each row
        const batch = db.batch();
        let batchCount = 0;
        const BATCH_SIZE = 450; // Firestore limit is 500

        for (let i = 0; i < rows.length; i++) {
            const row = rows[i];

            try {
                // Map columns to our schema
                const mappedRow: Record<string, string> = {};
                for (const [csvCol, ourField] of Object.entries(columnMapping)) {
                    if (row[csvCol] !== undefined) {
                        mappedRow[ourField] = row[csvCol];
                    }
                }

                // Validate the mapped row
                const candidateData = CandidateRowSchema.safeParse(mappedRow);
                if (!candidateData.success) {
                    result.errors.push({
                        row: i + 1,
                        error: candidateData.error.errors.map(e => e.message).join(', '),
                    });
                    continue;
                }

                const candidate = candidateData.data;

                // Check for duplicates
                const email = candidate.email?.toLowerCase();
                if (email && existingEmails.has(email)) {
                    if (dedupeStrategy === 'skip') {
                        result.skipped++;
                        continue;
                    }
                    // For 'merge' or 'update', we'll update the existing document
                }

                // Generate candidate ID
                const candidateId = email && existingEmails.has(email)
                    ? existingEmails.get(email)!
                    : `cand_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;

                // Parse skills
                const skillsArray = candidate.skills
                    ? candidate.skills.split(',').map(s => s.trim()).filter(Boolean)
                    : [];

                // Build candidate document
                const now = Timestamp.now();
                const candidateDoc = {
                    candidate_id: candidateId,
                    org_id: orgId,
                    name: candidate.name,
                    email: candidate.email || null,
                    personal: {
                        name: candidate.name,
                        email: candidate.email || null,
                        phone: candidate.phone || null,
                        location: candidate.location || null,
                        linkedin: candidate.linkedin_url || null,
                    },
                    professional: {
                        current_title: candidate.current_title || null,
                        current_company: candidate.current_company || null,
                        years_experience: candidate.years_experience || null,
                    },
                    skills: skillsArray,
                    all_skills: skillsArray.map(s => s.toLowerCase()),
                    source: source,
                    notes: candidate.notes || null,
                    created_at: now,
                    updated_at: now,
                    processing: {
                        status: 'imported',
                        imported_at: now.toDate().toISOString(),
                        needs_resume: true, // Flag that resume is missing
                    },
                };

                // Add to batch
                const docRef = db.collection('candidates').doc(candidateId);
                if (dedupeStrategy === 'merge' && existingEmails.has(email!)) {
                    batch.set(docRef, candidateDoc, { merge: true });
                } else {
                    batch.set(docRef, candidateDoc);
                }

                result.candidateIds.push(candidateId);
                result.imported++;
                batchCount++;

                // Commit batch if at limit
                if (batchCount >= BATCH_SIZE) {
                    await batch.commit();
                    console.log(`Committed batch of ${batchCount} candidates`);
                    batchCount = 0;
                }

            } catch (error) {
                console.error(`Error processing row ${i + 1}:`, error);
                result.errors.push({
                    row: i + 1,
                    error: error instanceof Error ? error.message : 'Unknown error',
                });
            }
        }

        // Commit final batch
        if (batchCount > 0) {
            await batch.commit();
            console.log(`Committed final batch of ${batchCount} candidates`);
        }

        // Generate embeddings for imported candidates
        console.log(`Generating embeddings for ${result.candidateIds.length} candidates...`);
        let embeddingCount = 0;

        for (const candidateId of result.candidateIds) {
            try {
                const candidateDoc = await db.collection('candidates').doc(candidateId).get();
                if (candidateDoc.exists) {
                    const data = candidateDoc.data()!;

                    // Build profile object for embedding
                    const profileForEmbedding = {
                        candidate_id: candidateId,
                        name: data.name,
                        current_role: data.professional?.current_title,
                        current_company: data.professional?.current_company,
                        skills: data.skills || [],
                        resume_analysis: {
                            career_trajectory: {
                                current_level: 'Unknown',
                                trajectory_type: 'Standard'
                            }
                        }
                    };

                    await vectorService.storeEmbedding(profileForEmbedding);
                    embeddingCount++;
                }
            } catch (error) {
                console.error(`Error generating embedding for ${candidateId}:`, error);
            }
        }

        console.log(`Generated ${embeddingCount} embeddings`);
        console.log(`Import complete: ${result.imported} imported, ${result.skipped} skipped, ${result.errors.length} errors`);

        return result;
    }
);

/**
 * Get column suggestions for CSV mapping
 */
export const suggestColumnMapping = onCall(
    {
        memory: '256MiB',
        timeoutSeconds: 30,
    },
    async (request): Promise<Record<string, string>> => {
        if (!request.auth) {
            throw new HttpsError('unauthenticated', 'Authentication required');
        }

        const { columns } = request.data as { columns: string[] };
        if (!columns || !Array.isArray(columns)) {
            throw new HttpsError('invalid-argument', 'columns array is required');
        }

        // Common column name mappings
        const mappings: Record<string, string[]> = {
            name: ['name', 'full name', 'fullname', 'candidate name', 'first name', 'firstname'],
            email: ['email', 'email address', 'e-mail', 'mail', 'candidate email'],
            phone: ['phone', 'phone number', 'telephone', 'mobile', 'cell'],
            current_title: ['title', 'job title', 'current title', 'position', 'role', 'current position'],
            current_company: ['company', 'current company', 'employer', 'organization', 'org'],
            location: ['location', 'city', 'address', 'region', 'area'],
            linkedin_url: ['linkedin', 'linkedin url', 'linkedin profile', 'profile url'],
            skills: ['skills', 'abilities', 'competencies', 'expertise', 'technologies'],
            years_experience: ['experience', 'years experience', 'years of experience', 'yoe', 'years'],
            notes: ['notes', 'comments', 'remarks', 'description'],
        };

        const suggestions: Record<string, string> = {};

        for (const column of columns) {
            const normalizedColumn = column.toLowerCase().trim();

            for (const [field, variants] of Object.entries(mappings)) {
                if (variants.some(v => normalizedColumn.includes(v) || v.includes(normalizedColumn))) {
                    suggestions[column] = field;
                    break;
                }
            }
        }

        return suggestions;
    }
);
