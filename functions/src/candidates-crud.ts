#!/usr/bin/env node
/**
 * Candidates CRUD Operations
 * Complete create, read, update, delete operations for candidate management
 */

import { onCall, HttpsError } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";
import { z } from "zod";
import { Storage } from "@google-cloud/storage";

// Initialize services
const firestore = admin.firestore();
const storage = new Storage();

// Validation Schemas
const CreateCandidateSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email().optional(),
  phone: z.string().max(20).optional(),
  location: z.string().max(100).optional(),
  resume_text: z.string().optional(),
  notes: z.string().max(1000).optional(),
});

const UpdateCandidateSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  email: z.string().email().optional(),
  phone: z.string().max(20).optional(),
  location: z.string().max(100).optional(),
  notes: z.string().max(1000).optional(),
  status: z.enum(['active', 'interviewing', 'hired', 'rejected', 'withdrawn']).optional(),
});

const SearchCandidatesSchema = z.object({
  query: z.string().max(500).optional(),
  filters: z.object({
    experience_level: z.string().optional(),
    skills: z.array(z.string()).optional(),
    location: z.string().optional(),
    availability: z.string().optional(),
    company_tier: z.string().optional(),
    leadership_experience: z.boolean().optional(),
    min_years_experience: z.number().min(0).max(50).optional(),
    max_years_experience: z.number().min(0).max(50).optional(),
  }).optional(),
  sort: z.object({
    field: z.enum(['created_at', 'updated_at', 'name', 'experience_years', 'overall_rating']),
    direction: z.enum(['asc', 'desc']),
  }).optional(),
  pagination: z.object({
    page: z.number().min(1).default(1),
    limit: z.number().min(1).max(100).default(20),
  }).optional(),
});

// Helper Functions
function validateAuth(request: any): { userId: string; orgId: string } {
  if (!request.auth) {
    throw new HttpsError("unauthenticated", "Authentication required");
  }
  
  const userId = request.auth.uid;
  const orgId = request.auth.token.org_id;
  
  if (!orgId) {
    throw new HttpsError("permission-denied", "Organization membership required");
  }
  
  return { userId, orgId };
}

async function validatePermissions(userId: string, permission: string): Promise<boolean> {
  const userDoc = await firestore.collection('users').doc(userId).get();
  
  if (!userDoc.exists) {
    throw new HttpsError("not-found", "User profile not found");
  }
  
  const userData = userDoc.data();
  return userData?.permissions?.[permission] === true;
}

function buildSearchQuery(orgId: string, filters: any = {}, sort: any = {}) {
  let query: admin.firestore.Query = firestore
    .collection('candidates')
    .where('org_id', '==', orgId);

  // Apply filters
  if (filters.experience_level) {
    query = query.where('searchable_data.experience_level', '==', filters.experience_level);
  }

  if (filters.skills && filters.skills.length > 0) {
    query = query.where('searchable_data.skills_combined', 'array-contains-any', filters.skills);
  }

  if (filters.location) {
    query = query.where('personal.location', '==', filters.location);
  }

  if (filters.company_tier) {
    query = query.where('analysis.company_pedigree.company_tier', '==', filters.company_tier);
  }

  if (filters.leadership_experience !== undefined) {
    query = query.where('analysis.leadership_scope.has_leadership', '==', filters.leadership_experience);
  }

  if (filters.min_years_experience) {
    query = query.where('analysis.career_trajectory.years_experience', '>=', filters.min_years_experience);
  }

  // Apply sorting
  const sortField = sort.field || 'updated_at';
  const sortDirection = sort.direction || 'desc';
  query = query.orderBy(sortField, sortDirection);

  return query;
}

/**
 * Create a new candidate
 */
export const createCandidate = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);
    
    // Check permissions
    const canCreate = await validatePermissions(userId, 'can_edit_candidates');
    if (!canCreate) {
      throw new HttpsError("permission-denied", "Insufficient permissions to create candidates");
    }

    // Validate input
    let validatedInput;
    try {
      validatedInput = CreateCandidateSchema.parse(request.data);
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
      }
      throw new HttpsError("invalid-argument", "Invalid request data");
    }

    try {
      const candidateId = firestore.collection('candidates').doc().id;
      
      const candidateData = {
        candidate_id: candidateId,
        org_id: orgId,
        created_by: userId,
        created_at: admin.firestore.FieldValue.serverTimestamp(),
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
        
        // Basic Information
        personal: {
          name: validatedInput.name,
          email: validatedInput.email || null,
          phone: validatedInput.phone || null,
          location: validatedInput.location || null,
        },
        
        // Documents
        documents: {
          resume_text: validatedInput.resume_text || null,
        },
        
        // Processing Status
        processing: {
          status: 'pending',
          local_analysis_completed: false,
          embedding_generated: false,
          last_processed: null,
        },
        
        // Search Data (will be populated after analysis)
        searchable_data: {
          skills_combined: [],
          experience_level: 'unknown',
          industries: [],
          locations: validatedInput.location ? [validatedInput.location] : [],
        },
        
        // User Interactions
        interactions: {
          views: 0,
          bookmarks: [],
          notes: validatedInput.notes ? [{
            user_id: userId,
            note: validatedInput.notes,
            created_at: admin.firestore.FieldValue.serverTimestamp(),
          }] : [],
          status_updates: [{
            status: 'created',
            updated_by: userId,
            updated_at: admin.firestore.FieldValue.serverTimestamp(),
          }],
        },
        
        // Privacy
        privacy: {
          is_public: false,
          consent_given: false,
          gdpr_compliant: true,
        },
      };

      await firestore.collection('candidates').doc(candidateId).set(candidateData);
      
      // Add to processing queue if resume text provided
      if (validatedInput.resume_text) {
        await firestore.collection('processing_queue').add({
          candidate_id: candidateId,
          stage: 'awaiting_analysis',
          structured_data: {
            candidate_id: candidateId,
            raw_text: validatedInput.resume_text,
            extracted_at: new Date().toISOString(),
          },
          created_at: admin.firestore.FieldValue.serverTimestamp(),
        });
      }

      return {
        success: true,
        candidate_id: candidateId,
        data: candidateData,
      };
    } catch (error) {
      console.error("Error creating candidate:", error);
      throw new HttpsError("internal", "Failed to create candidate");
    }
  }
);

/**
 * Get a single candidate by ID
 */
export const getCandidate = onCall(
  {
    memory: "256MiB",
    timeoutSeconds: 30,
  },
  async (request) => {
    const { orgId } = validateAuth(request);
    const { candidate_id } = request.data;

    if (!candidate_id) {
      throw new HttpsError("invalid-argument", "Candidate ID is required");
    }

    try {
      const candidateDoc = await firestore.collection('candidates').doc(candidate_id).get();

      if (!candidateDoc.exists) {
        throw new HttpsError("not-found", "Candidate not found");
      }

      const candidateData = candidateDoc.data();
      
      // Check organization access
      if (candidateData?.org_id !== orgId) {
        throw new HttpsError("permission-denied", "Access denied to this candidate");
      }

      // Increment view count
      await candidateDoc.ref.update({
        'interactions.views': admin.firestore.FieldValue.increment(1),
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
      });

      return {
        success: true,
        data: candidateData,
      };
    } catch (error) {
      if (error instanceof HttpsError) throw error;
      console.error("Error getting candidate:", error);
      throw new HttpsError("internal", "Failed to retrieve candidate");
    }
  }
);

/**
 * Update an existing candidate
 */
export const updateCandidate = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);
    const { candidate_id, ...updateData } = request.data;

    if (!candidate_id) {
      throw new HttpsError("invalid-argument", "Candidate ID is required");
    }

    // Check permissions
    const canEdit = await validatePermissions(userId, 'can_edit_candidates');
    if (!canEdit) {
      throw new HttpsError("permission-denied", "Insufficient permissions to edit candidates");
    }

    // Validate input
    let validatedInput;
    try {
      validatedInput = UpdateCandidateSchema.parse(updateData);
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
      }
      throw new HttpsError("invalid-argument", "Invalid request data");
    }

    try {
      const candidateDoc = await firestore.collection('candidates').doc(candidate_id).get();

      if (!candidateDoc.exists) {
        throw new HttpsError("not-found", "Candidate not found");
      }

      const existingData = candidateDoc.data();
      
      // Check organization access
      if (existingData?.org_id !== orgId) {
        throw new HttpsError("permission-denied", "Access denied to this candidate");
      }

      // Build update object
      const updateObj: any = {
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
      };

      // Update personal information
      if (validatedInput.name) updateObj['personal.name'] = validatedInput.name;
      if (validatedInput.email !== undefined) updateObj['personal.email'] = validatedInput.email;
      if (validatedInput.phone !== undefined) updateObj['personal.phone'] = validatedInput.phone;
      if (validatedInput.location !== undefined) {
        updateObj['personal.location'] = validatedInput.location;
        // Update searchable locations
        updateObj['searchable_data.locations'] = validatedInput.location ? [validatedInput.location] : [];
      }

      // Add status update if status changed
      if (validatedInput.status && validatedInput.status !== existingData?.status) {
        updateObj['interactions.status_updates'] = admin.firestore.FieldValue.arrayUnion({
          status: validatedInput.status,
          updated_by: userId,
          updated_at: admin.firestore.FieldValue.serverTimestamp(),
        });
      }

      // Add note if provided
      if (validatedInput.notes) {
        updateObj['interactions.notes'] = admin.firestore.FieldValue.arrayUnion({
          user_id: userId,
          note: validatedInput.notes,
          created_at: admin.firestore.FieldValue.serverTimestamp(),
        });
      }

      await candidateDoc.ref.update(updateObj);

      // Get updated document
      const updatedDoc = await candidateDoc.ref.get();

      return {
        success: true,
        data: updatedDoc.data(),
      };
    } catch (error) {
      if (error instanceof HttpsError) throw error;
      console.error("Error updating candidate:", error);
      throw new HttpsError("internal", "Failed to update candidate");
    }
  }
);

/**
 * Delete a candidate
 */
export const deleteCandidate = onCall(
  {
    memory: "256MiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);
    const { candidate_id } = request.data;

    if (!candidate_id) {
      throw new HttpsError("invalid-argument", "Candidate ID is required");
    }

    // Check permissions
    const canEdit = await validatePermissions(userId, 'can_edit_candidates');
    if (!canEdit) {
      throw new HttpsError("permission-denied", "Insufficient permissions to delete candidates");
    }

    try {
      const candidateDoc = await firestore.collection('candidates').doc(candidate_id).get();

      if (!candidateDoc.exists) {
        throw new HttpsError("not-found", "Candidate not found");
      }

      const candidateData = candidateDoc.data();
      
      // Check organization access
      if (candidateData?.org_id !== orgId) {
        throw new HttpsError("permission-denied", "Access denied to this candidate");
      }

      // Use batch for atomic deletion
      const batch = firestore.batch();

      // Delete candidate document
      batch.delete(candidateDoc.ref);

      // Delete related embeddings
      const embeddingsQuery = await firestore
        .collection('embeddings')
        .where('candidate_id', '==', candidate_id)
        .get();

      embeddingsQuery.docs.forEach(doc => {
        batch.delete(doc.ref);
      });

      // Clean up processing queue
      const processingQuery = await firestore
        .collection('processing_queue')
        .where('candidate_id', '==', candidate_id)
        .get();

      processingQuery.docs.forEach(doc => {
        batch.delete(doc.ref);
      });

      await batch.commit();

      // Delete files from Cloud Storage (async, don't wait)
      if (candidateData?.documents?.resume_file_url) {
        const bucketName = "headhunter-ai-0088-files";
        storage.bucket(bucketName).file(candidateData.documents.resume_file_url).delete().catch(console.error);
      }

      return {
        success: true,
        candidate_id: candidate_id,
      };
    } catch (error) {
      if (error instanceof HttpsError) throw error;
      console.error("Error deleting candidate:", error);
      throw new HttpsError("internal", "Failed to delete candidate");
    }
  }
);

/**
 * Search candidates with advanced filtering
 */
export const searchCandidates = onCall(
  {
    memory: "1GiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);

    // Check permissions
    const canView = await validatePermissions(userId, 'can_view_candidates');
    if (!canView) {
      throw new HttpsError("permission-denied", "Insufficient permissions to view candidates");
    }

    // Validate input
    let validatedInput;
    try {
      validatedInput = SearchCandidatesSchema.parse(request.data);
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
      }
      throw new HttpsError("invalid-argument", "Invalid request data");
    }

    try {
      const { query: searchQuery, filters, sort, pagination } = validatedInput;
      const page = pagination?.page || 1;
      const limit = pagination?.limit || 20;
      const offset = (page - 1) * limit;

      // Build Firestore query
      let firestoreQuery = buildSearchQuery(orgId, filters, sort);

      // Get total count for pagination
      const countSnapshot = await firestoreQuery.count().get();
      const totalCount = countSnapshot.data().count;

      // Apply pagination
      const resultsSnapshot = await firestoreQuery
        .offset(offset)
        .limit(limit)
        .get();

      const candidates = resultsSnapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data(),
      }));

      // If text query provided, perform additional filtering
      let filteredCandidates = candidates;
      if (searchQuery && searchQuery.trim()) {
        const queryLower = searchQuery.toLowerCase();
        filteredCandidates = candidates.filter((candidate: any) => {
          const name = candidate.personal?.name?.toLowerCase() || '';
          const skills = (candidate.searchable_data?.skills_combined || []).join(' ').toLowerCase();
          const resumeText = candidate.documents?.resume_text?.toLowerCase() || '';
          const location = candidate.personal?.location?.toLowerCase() || '';
          
          return name.includes(queryLower) || 
                 skills.includes(queryLower) || 
                 resumeText.includes(queryLower) ||
                 location.includes(queryLower);
        });
      }

      // Calculate pagination info
      const totalPages = Math.ceil(totalCount / limit);
      const hasNextPage = page < totalPages;
      const hasPreviousPage = page > 1;

      return {
        success: true,
        data: {
          candidates: filteredCandidates,
          pagination: {
            page,
            limit,
            total_count: totalCount,
            total_pages: totalPages,
            has_next_page: hasNextPage,
            has_previous_page: hasPreviousPage,
          },
          filters_applied: filters || {},
          sort_applied: sort || { field: 'updated_at', direction: 'desc' },
          search_query: searchQuery || null,
        },
      };
    } catch (error) {
      if (error instanceof HttpsError) throw error;
      console.error("Error searching candidates:", error);
      throw new HttpsError("internal", "Failed to search candidates");
    }
  }
);

/**
 * Get candidates list with pagination
 */
export const getCandidates = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 30,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);

    // Check permissions
    const canView = await validatePermissions(userId, 'can_view_candidates');
    if (!canView) {
      throw new HttpsError("permission-denied", "Insufficient permissions to view candidates");
    }

    const { page = 1, limit = 20, sort_by = 'updated_at', sort_order = 'desc' } = request.data;

    try {
      const offset = (page - 1) * limit;

      // Get total count
      const countSnapshot = await firestore
        .collection('candidates')
        .where('org_id', '==', orgId)
        .count()
        .get();
      const totalCount = countSnapshot.data().count;

      // Get paginated results
      const candidatesSnapshot = await firestore
        .collection('candidates')
        .where('org_id', '==', orgId)
        .orderBy(sort_by, sort_order as any)
        .offset(offset)
        .limit(limit)
        .get();

      const candidates = candidatesSnapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data(),
      }));

      const totalPages = Math.ceil(totalCount / limit);

      return {
        success: true,
        data: {
          candidates,
          pagination: {
            page,
            limit,
            total_count: totalCount,
            total_pages: totalPages,
            has_next_page: page < totalPages,
            has_previous_page: page > 1,
          },
        },
      };
    } catch (error) {
      console.error("Error getting candidates:", error);
      throw new HttpsError("internal", "Failed to retrieve candidates");
    }
  }
);

/**
 * Add note to candidate
 */
export const addCandidateNote = onCall(
  {
    memory: "256MiB",
    timeoutSeconds: 30,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);
    const { candidate_id, note } = request.data;

    if (!candidate_id || !note) {
      throw new HttpsError("invalid-argument", "Candidate ID and note are required");
    }

    if (note.length > 1000) {
      throw new HttpsError("invalid-argument", "Note too long (max 1000 characters)");
    }

    try {
      const candidateDoc = await firestore.collection('candidates').doc(candidate_id).get();

      if (!candidateDoc.exists) {
        throw new HttpsError("not-found", "Candidate not found");
      }

      const candidateData = candidateDoc.data();
      
      // Check organization access
      if (candidateData?.org_id !== orgId) {
        throw new HttpsError("permission-denied", "Access denied to this candidate");
      }

      const noteObj = {
        user_id: userId,
        note: note.trim(),
        created_at: admin.firestore.FieldValue.serverTimestamp(),
      };

      await candidateDoc.ref.update({
        'interactions.notes': admin.firestore.FieldValue.arrayUnion(noteObj),
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
      });

      return {
        success: true,
        note: noteObj,
      };
    } catch (error) {
      if (error instanceof HttpsError) throw error;
      console.error("Error adding note:", error);
      throw new HttpsError("internal", "Failed to add note");
    }
  }
);

/**
 * Bookmark/unbookmark candidate
 */
export const toggleCandidateBookmark = onCall(
  {
    memory: "256MiB",
    timeoutSeconds: 30,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);
    const { candidate_id } = request.data;

    if (!candidate_id) {
      throw new HttpsError("invalid-argument", "Candidate ID is required");
    }

    try {
      const candidateDoc = await firestore.collection('candidates').doc(candidate_id).get();

      if (!candidateDoc.exists) {
        throw new HttpsError("not-found", "Candidate not found");
      }

      const candidateData = candidateDoc.data();
      
      // Check organization access
      if (candidateData?.org_id !== orgId) {
        throw new HttpsError("permission-denied", "Access denied to this candidate");
      }

      const currentBookmarks = candidateData?.interactions?.bookmarks || [];
      const isBookmarked = currentBookmarks.includes(userId);

      const updateObj: any = isBookmarked
        ? { 'interactions.bookmarks': admin.firestore.FieldValue.arrayRemove(userId) }
        : { 'interactions.bookmarks': admin.firestore.FieldValue.arrayUnion(userId) };

      updateObj.updated_at = admin.firestore.FieldValue.serverTimestamp();

      await candidateDoc.ref.update(updateObj);

      return {
        success: true,
        bookmarked: !isBookmarked,
      };
    } catch (error) {
      if (error instanceof HttpsError) throw error;
      console.error("Error toggling bookmark:", error);
      throw new HttpsError("internal", "Failed to toggle bookmark");
    }
  }
);

/**
 * Bulk operations for candidates
 */
export const bulkCandidateOperations = onCall(
  {
    memory: "1GiB",
    timeoutSeconds: 300,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);
    const { operation, candidate_ids, data } = request.data;

    if (!operation || !candidate_ids || !Array.isArray(candidate_ids)) {
      throw new HttpsError("invalid-argument", "Operation and candidate IDs array are required");
    }

    if (candidate_ids.length > 100) {
      throw new HttpsError("invalid-argument", "Too many candidates (max 100)");
    }

    // Check permissions
    const canEdit = await validatePermissions(userId, 'can_edit_candidates');
    if (!canEdit) {
      throw new HttpsError("permission-denied", "Insufficient permissions for bulk operations");
    }

    try {
      const batch = firestore.batch();
      const results = [];

      for (const candidate_id of candidate_ids) {
        const candidateDoc = await firestore.collection('candidates').doc(candidate_id).get();
        
        if (!candidateDoc.exists) {
          results.push({ candidate_id, status: 'not_found' });
          continue;
        }

        const candidateData = candidateDoc.data();
        
        // Check organization access
        if (candidateData?.org_id !== orgId) {
          results.push({ candidate_id, status: 'access_denied' });
          continue;
        }

        let updateObj: any = {
          updated_at: admin.firestore.FieldValue.serverTimestamp(),
        };

        switch (operation) {
          case 'delete':
            batch.delete(candidateDoc.ref);
            results.push({ candidate_id, status: 'deleted' });
            break;
            
          case 'update_status':
            if (!data?.status) {
              results.push({ candidate_id, status: 'invalid_status' });
              continue;
            }
            updateObj['interactions.status_updates'] = admin.firestore.FieldValue.arrayUnion({
              status: data.status,
              updated_by: userId,
              updated_at: admin.firestore.FieldValue.serverTimestamp(),
            });
            batch.update(candidateDoc.ref, updateObj);
            results.push({ candidate_id, status: 'updated' });
            break;
            
          case 'add_tag':
            if (!data?.tag) {
              results.push({ candidate_id, status: 'invalid_tag' });
              continue;
            }
            updateObj['searchable_data.tags'] = admin.firestore.FieldValue.arrayUnion(data.tag);
            batch.update(candidateDoc.ref, updateObj);
            results.push({ candidate_id, status: 'tagged' });
            break;
            
          default:
            results.push({ candidate_id, status: 'invalid_operation' });
        }
      }

      await batch.commit();

      return {
        success: true,
        operation,
        total_processed: candidate_ids.length,
        results,
      };
    } catch (error) {
      console.error("Error in bulk operation:", error);
      throw new HttpsError("internal", "Failed to complete bulk operation");
    }
  }
);

/**
 * Get candidate statistics for dashboard
 */
export const getCandidateStats = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);

    // Check permissions
    const canView = await validatePermissions(userId, 'can_view_candidates');
    if (!canView) {
      throw new HttpsError("permission-denied", "Insufficient permissions to view statistics");
    }

    try {
      const candidatesRef = firestore.collection('candidates').where('org_id', '==', orgId);

      // Get total count
      const totalSnapshot = await candidatesRef.count().get();
      const totalCandidates = totalSnapshot.data().count;

      // Get processed count
      const processedSnapshot = await candidatesRef
        .where('processing.local_analysis_completed', '==', true)
        .count()
        .get();
      const processedCandidates = processedSnapshot.data().count;

      // Get candidates by experience level
      const experienceLevels = ['entry', 'mid', 'senior', 'lead', 'executive'];
      const experienceStats: { [key: string]: number } = {};
      
      for (const level of experienceLevels) {
        const snapshot = await candidatesRef
          .where('searchable_data.experience_level', '==', level)
          .count()
          .get();
        experienceStats[level] = snapshot.data().count;
      }

      // Get recent activity (last 7 days)
      const sevenDaysAgo = new Date();
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
      
      const recentSnapshot = await candidatesRef
        .where('created_at', '>=', sevenDaysAgo)
        .count()
        .get();
      const recentCandidates = recentSnapshot.data().count;

      return {
        success: true,
        stats: {
          total_candidates: totalCandidates,
          processed_candidates: processedCandidates,
          pending_processing: totalCandidates - processedCandidates,
          recent_candidates: recentCandidates,
          experience_levels: experienceStats,
          processing_completion_rate: totalCandidates > 0 
            ? Math.round((processedCandidates / totalCandidates) * 100) 
            : 0,
        },
      };
    } catch (error) {
      console.error("Error getting candidate stats:", error);
      throw new HttpsError("internal", "Failed to retrieve statistics");
    }
  }
);