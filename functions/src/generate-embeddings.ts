/**
 * Cloud Function to generate embeddings for all candidates
 * Uses Vertex AI text-embedding-004 model
 */
import * as functions from 'firebase-functions/v2';
import { getFirestore } from 'firebase-admin/firestore';
import { VectorSearchService } from './vector-search';

const db = getFirestore();

export const generateAllEmbeddings = functions.https.onRequest(
  {
    memory: '1GiB',
    timeoutSeconds: 540,
  },
  async (req, res): Promise<void> => {
    console.log('Starting embedding generation for all candidates...');
    
    try {
      const vectorService = new VectorSearchService();
      
      // Get all candidates from Firestore
      const candidatesSnapshot = await db.collection('candidates').get();
      const candidates = candidatesSnapshot.docs;
      
      console.log(`Found ${candidates.length} candidates to process`);
      
      let processedCount = 0;
      let errorCount = 0;
      
      for (const candidateDoc of candidates) {
        try {
          const candidateData = candidateDoc.data();
          const candidateId = candidateDoc.id;
          
          console.log(`Processing embeddings for candidate ${processedCount + 1}/${candidates.length}: ${candidateData.name}`);
          
          // Create text content for embedding
          const textContent = [
            candidateData.name || '',
            candidateData.current_role || '',
            candidateData.current_company || '',
            (candidateData.resume_analysis?.technical_skills || []).join(' '),
            (candidateData.resume_analysis?.soft_skills || []).join(' '),
            (candidateData.resume_analysis?.career_trajectory?.current_level || ''),
            (candidateData.resume_analysis?.career_trajectory?.trajectory_type || ''),
            (candidateData.resume_analysis?.company_pedigree?.tier_level || ''),
            (candidateData.recruiter_insights?.strengths || []).join(' '),
            (candidateData.recruiter_insights?.key_themes || []).join(' ')
          ].filter(Boolean).join(' ');
          
          // Generate embedding
          const embedding = await vectorService.generateEmbedding(textContent);
          
          // Store embedding in separate collection for efficient vector search
          await db.collection('embeddings').doc(candidateId).set({
            candidate_id: candidateId,
            embedding: embedding,
            content_hash: textContent.substring(0, 100), // First 100 chars for reference
            updated_at: new Date().toISOString(),
            metadata: {
              technical_skills_count: candidateData.resume_analysis?.technical_skills?.length || 0,
              years_experience: candidateData.resume_analysis?.years_experience || 0,
              current_level: candidateData.resume_analysis?.career_trajectory?.current_level,
              overall_score: candidateData.overall_score || 0
            }
          });
          
          processedCount++;
          
          // Small delay to avoid overwhelming the API
          if (processedCount % 10 === 0) {
            console.log(`Processed ${processedCount}/${candidates.length} candidates...`);
            await new Promise(resolve => setTimeout(resolve, 1000));
          }
          
        } catch (error) {
          console.error(`Error processing candidate ${candidateDoc.id}:`, error);
          errorCount++;
        }
      }
      
      console.log(`Embedding generation complete!`);
      console.log(`Processed: ${processedCount}, Errors: ${errorCount}`);
      
      res.status(200).json({
        success: true,
        message: `Generated embeddings for ${processedCount} candidates`,
        processed: processedCount,
        errors: errorCount,
        total: candidates.length
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
    memory: '512MiB',
    timeoutSeconds: 60,
  },
  async (request) => {
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
      
      // Create text content for embedding
      const textContent = [
        candidateData.name || '',
        candidateData.current_role || '',
        candidateData.current_company || '',
        (candidateData.resume_analysis?.technical_skills || []).join(' '),
        (candidateData.resume_analysis?.soft_skills || []).join(' '),
        (candidateData.resume_analysis?.career_trajectory?.current_level || ''),
        (candidateData.resume_analysis?.career_trajectory?.trajectory_type || ''),
        (candidateData.resume_analysis?.company_pedigree?.tier_level || ''),
        (candidateData.recruiter_insights?.strengths || []).join(' '),
        (candidateData.recruiter_insights?.key_themes || []).join(' ')
      ].filter(Boolean).join(' ');
      
      // Generate embedding
      const embedding = await vectorService.generateEmbedding(textContent);
      
      // Store embedding
      await db.collection('embeddings').doc(candidateId).set({
        candidate_id: candidateId,
        embedding: embedding,
        content_hash: textContent.substring(0, 100),
        updated_at: new Date().toISOString(),
        metadata: {
          technical_skills_count: candidateData.resume_analysis?.technical_skills?.length || 0,
          years_experience: candidateData.resume_analysis?.years_experience || 0,
          current_level: candidateData.resume_analysis?.career_trajectory?.current_level,
          overall_score: candidateData.overall_score || 0
        }
      });
      
      return {
        success: true,
        message: `Generated embedding for candidate ${candidateId}`,
        candidateId,
        embeddingSize: embedding.length
      };
      
    } catch (error) {
      console.error('Error generating embedding:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      throw new functions.https.HttpsError('internal', `Failed to generate embedding: ${errorMessage}`);
    }
  }
);