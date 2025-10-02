/**
 * Cloud Function to upload processed candidates to Firestore
 * This bypasses security rules since Cloud Functions have admin access
 */
import * as functions from 'firebase-functions/v2';
import { getFirestore } from 'firebase-admin/firestore';
import { initializeApp } from 'firebase-admin/app';
import * as fs from 'fs';
import * as path from 'path';

const CANONICAL_REPO = process.env.HEADHUNTER_HOME ?? '/Volumes/Extreme Pro/myprojects/headhunter';
const DEFAULT_CANDIDATES_PATH = process.env.HEADHUNTER_CANDIDATES_PATH ?? path.join(CANONICAL_REPO, 'scripts', 'comprehensive_candidates_processed.json');

// Initialize Firebase Admin if not already done
try {
  initializeApp();
} catch (e) {
  // App already initialized
}

const db = getFirestore();

export const uploadCandidates = functions.https.onCall(
  { 
    memory: '1GiB',
    timeoutSeconds: 540,
  },
  async (request) => {
    console.log('Starting candidate upload process...');
    
    try {
      // Read the comprehensive processed candidates file
      const candidatesPath = DEFAULT_CANDIDATES_PATH;
      
      if (!fs.existsSync(candidatesPath)) {
        throw new Error(`Candidates file not found: ${candidatesPath}`);
      }
      
      const candidatesData = JSON.parse(fs.readFileSync(candidatesPath, 'utf8'));
      console.log(`Found ${candidatesData.length} candidates to upload`);
      
      const batch = db.batch();
      let uploadCount = 0;
      
      for (const candidate of candidatesData) {
        const candidateRef = db.collection('candidates').doc(candidate.candidate_id);
        batch.set(candidateRef, candidate);
        uploadCount++;
        
        // Firestore batch has limit of 500 operations
        if (uploadCount % 450 === 0) {
          console.log(`Committing batch of ${uploadCount} candidates...`);
          await batch.commit();
        }
      }
      
      // Commit final batch
      if (uploadCount % 450 !== 0) {
        console.log(`Committing final batch...`);
        await batch.commit();
      }
      
      console.log(`Successfully uploaded ${uploadCount} candidates to Firestore`);
      
      return {
        success: true,
        message: `Uploaded ${uploadCount} candidates successfully`,
        candidateCount: uploadCount
      };
      
    } catch (error) {
      console.error('Error uploading candidates:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      throw new functions.https.HttpsError(
        'internal',
        `Failed to upload candidates: ${errorMessage}`
      );
    }
  }
);

// HTTP version for easier testing
export const uploadCandidatesHttp = functions.https.onRequest(
  {
    memory: '1GiB',
    timeoutSeconds: 540,
  },
  async (req, res): Promise<void> => {
    console.log('HTTP upload request received...');
    
    try {
      // Read the comprehensive processed candidates file
      const candidatesPath = DEFAULT_CANDIDATES_PATH;
      
      if (!fs.existsSync(candidatesPath)) {
        res.status(404).json({ 
          error: `Candidates file not found: ${candidatesPath}` 
        });
        return;
      }
      
      const candidatesData = JSON.parse(fs.readFileSync(candidatesPath, 'utf8'));
      console.log(`Found ${candidatesData.length} candidates to upload`);
      
      const batch = db.batch();
      let uploadCount = 0;
      
      for (const candidate of candidatesData) {
        const candidateRef = db.collection('candidates').doc(candidate.candidate_id);
        batch.set(candidateRef, candidate);
        uploadCount++;
      }
      
      console.log(`Committing batch of ${uploadCount} candidates...`);
      await batch.commit();
      
      console.log(`Successfully uploaded ${uploadCount} candidates to Firestore`);
      
      res.status(200).json({
        success: true,
        message: `Uploaded ${uploadCount} candidates successfully`,
        candidateCount: uploadCount
      });
      
    } catch (error) {
      console.error('Error uploading candidates:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      res.status(500).json({ 
        error: `Failed to upload candidates: ${errorMessage}` 
      });
    }
  }
);