/**
 * Cloud Function to generate embeddings for all candidates
 * Uses Vertex AI text-embedding-004 model
 */
import * as functions from 'firebase-functions/v2';
import { getFirestore } from 'firebase-admin/firestore';
import { VectorSearchService } from './vector-search';

const db = getFirestore();

import { defineSecret } from "firebase-functions/params";

const dbPostgresPassword = defineSecret("db-postgres-password");

export const generateAllEmbeddings = functions.https.onRequest(
  {
    memory: '2GiB',
    timeoutSeconds: 540,
    secrets: [dbPostgresPassword],
    vpcConnector: "svpc-us-central1",
    vpcConnectorEgressSettings: "PRIVATE_RANGES_ONLY",
  },
  async (req, res): Promise<void> => {
    // Inject DB configuration for Cloud SQL connection
    process.env.PGVECTOR_PASSWORD = dbPostgresPassword.value();
    process.env.PGVECTOR_HOST = "10.159.0.2";
    process.env.PGVECTOR_USER = "postgres";
    process.env.PGVECTOR_DATABASE = "headhunter";

    console.log('Starting embedding generation for all candidates...');

    try {
      const vectorService = new VectorSearchService();

      let lastDoc = null;
      let hasMore = true;
      let processedCount = 0;
      let errorCount = 0;
      const BATCH_SIZE = 100;

      while (hasMore) {
        let query = db.collection('candidates').limit(BATCH_SIZE);
        if (lastDoc) {
          query = query.startAfter(lastDoc);
        }

        const snapshot = await query.get();
        if (snapshot.empty) {
          hasMore = false;
          break;
        }

        lastDoc = snapshot.docs[snapshot.docs.length - 1];
        const candidates = snapshot.docs;

        console.log(`Processing batch of ${candidates.length} candidates...`);

        for (const candidateDoc of candidates) {
          try {
            const candidateData = candidateDoc.data();
            const candidateId = candidateDoc.id;

            // Store embedding using VectorSearchService (handles pgvector or Firestore)
            await vectorService.storeEmbedding({
              ...candidateData,
              candidate_id: candidateId
            });

            processedCount++;
          } catch (error) {
            console.error(`Error processing candidate ${candidateDoc.id}:`, error);
            errorCount++;
          }
        }

        console.log(`Processed total: ${processedCount}`);
      }

      console.log(`Embedding generation complete!`);
      console.log(`Processed: ${processedCount}, Errors: ${errorCount}`);

      res.status(200).json({
        success: true,
        message: `Generated embeddings for ${processedCount} candidates`,
        processed: processedCount,
        errors: errorCount
      });

    } catch (error) {
      console.error('Error in embedding generation:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      res.status(500).json({
        error: `Failed to generate embeddings: ${errorMessage}`
      });
    }
  }
);

export const generateEmbeddingForCandidate = functions.https.onCall(
  {
    memory: '1GiB',
    timeoutSeconds: 120,
    secrets: [dbPostgresPassword],
    vpcConnector: "svpc-us-central1",
    vpcConnectorEgressSettings: "PRIVATE_RANGES_ONLY",
  },
  async (request) => {
    // Inject PgVector password from secret
    process.env.PGVECTOR_PASSWORD = dbPostgresPassword.value();
    process.env.PGVECTOR_HOST = "10.159.0.2";
    process.env.PGVECTOR_USER = "postgres";
    process.env.PGVECTOR_DATABASE = "headhunter";

    const { candidateId } = request.data;

    if (!candidateId) {
      throw new functions.https.HttpsError('invalid-argument', 'Candidate ID is required');
    }

    try {
      const vectorService = new VectorSearchService();

      // Get candidate data
      const candidateDoc = await db.collection('candidates').doc(candidateId).get();
      if (!candidateDoc.exists) {
        throw new functions.https.HttpsError('not-found', 'Candidate not found');
      }

      const candidateData = candidateDoc.data();
      if (!candidateData) {
        throw new functions.https.HttpsError('not-found', 'Candidate data not found');
      }

      // Store embedding using VectorSearchService (handles PgVector)
      await vectorService.storeEmbedding({
        ...candidateData,
        candidate_id: candidateId
      });

      // Update candidate document to mark embedding as generated
      await db.collection('candidates').doc(candidateId).update({
        'processing.embedding_generated': true
      });

      return {
        success: true,
        message: `Generated embedding for candidate ${candidateId}`,
        candidateId
      };

    } catch (error) {
      console.error('Error generating embedding:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      throw new functions.https.HttpsError('internal', `Failed to generate embedding: ${errorMessage}`);
    }
  }
);
