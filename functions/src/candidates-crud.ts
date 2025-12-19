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
  candidate_id: z.string().max(100).optional(), // Accept frontend-provided ID
  name: z.string().max(100).optional().default("Unknown Candidate"),
  email: z.string().email().optional(),
  phone: z.string().max(20).optional(),
  location: z.string().max(100).optional(),
  resume_text: z.string().optional(),
  resume_url: z.string().optional(),
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

/**
 * Levenshtein distance - measures how many edits needed to transform one string to another
 * Used for fuzzy matching names with typos
 */
function levenshteinDistance(str1: string, str2: string): number {
  const m = str1.length;
  const n = str2.length;

  // Create matrix
  const dp: number[][] = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0));

  // Initialize
  for (let i = 0; i <= m; i++) dp[i][0] = i;
  for (let j = 0; j <= n; j++) dp[0][j] = j;

  // Fill matrix
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (str1[i - 1] === str2[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1];
      } else {
        dp[i][j] = 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
      }
    }
  }

  return dp[m][n];
}

/**
 * Fuzzy match - checks if query matches target with tolerance for typos
 * Returns true if any word in query fuzzy-matches any word in target
 */
function fuzzyMatch(query: string, target: string, maxDistance: number = 2): boolean {
  if (!query || !target) return false;

  // First check exact contains (fast path)
  if (target.includes(query)) return true;

  // Split into words and check each
  const queryWords = query.split(/\s+/).filter(w => w.length > 2);
  const targetWords = target.split(/\s+/).filter(w => w.length > 2);

  for (const qWord of queryWords) {
    // Check if this query word matches any target word
    let wordMatched = false;

    for (const tWord of targetWords) {
      // Exact contains
      if (tWord.includes(qWord) || qWord.includes(tWord)) {
        wordMatched = true;
        break;
      }

      // Fuzzy match - allow edit distance proportional to word length
      const allowedDistance = Math.min(maxDistance, Math.floor(qWord.length / 3));
      if (levenshteinDistance(qWord, tWord) <= allowedDistance) {
        wordMatched = true;
        break;
      }
    }

    if (!wordMatched) return false; // All query words must match
  }

  return queryWords.length > 0;
}

function buildSearchQuery(orgId: string, filters: any = {}, sort: any = {}) {
  // Ella org (org_ella_main) sees ALL candidates regardless of org
  // This is a policy exception for the main recruiting agency
  const isEllaOrg = orgId === 'org_ella_main';

  let query: admin.firestore.Query = isEllaOrg
    ? firestore.collection('candidates')
    : firestore.collection('candidates').where('org_id', '==', orgId);

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
      // Use frontend-provided candidate_id if given, otherwise generate new one
      const candidateId = validatedInput.candidate_id || firestore.collection('candidates').doc().id;
      console.log(`Creating candidate with ID: ${candidateId}`);

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
          resume_ref: validatedInput.resume_url || null,
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
            created_at: admin.firestore.Timestamp.now(),
          }] : [],
          status_updates: [{
            status: 'created',
            updated_by: userId,
            updated_at: admin.firestore.Timestamp.now(),
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
          updated_at: admin.firestore.Timestamp.now(),
        });
      }

      // Add note if provided
      if (validatedInput.notes) {
        updateObj['interactions.notes'] = admin.firestore.FieldValue.arrayUnion({
          user_id: userId,
          note: validatedInput.notes,
          created_at: admin.firestore.Timestamp.now(),
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

      // Build Firestore query
      let firestoreQuery = buildSearchQuery(orgId, filters, sort);

      // For TEXT SEARCH: We need to fetch a larger batch first, then filter, then paginate
      // This is because Firestore doesn't support full-text search
      const hasTextSearch = searchQuery && searchQuery.trim();

      let candidates: any[];
      let totalCount: number;

      if (hasTextSearch) {
        // For text search, fetch a large batch and filter client-side
        // Then apply pagination to the filtered results
        const largeBatchSize = 5000; // Fetch up to 5000 candidates for text search
        const snapshot = await firestoreQuery.limit(largeBatchSize).get();

        const queryLower = searchQuery.toLowerCase();
        const allCandidates = snapshot.docs.map(doc => ({
          id: doc.id,
          ...doc.data(),
        }));

        // Filter by text search - check both legacy and new field structures
        // Use fuzzyMatch for typo tolerance (e.g., "trontini" matches "trentini")
        const filteredCandidates = allCandidates.filter((candidate: any) => {
          const name = (candidate.personal?.name || candidate.name || '').toLowerCase();
          const title = (candidate.current_role || candidate.title || candidate.current_title || '').toLowerCase();
          const company = (candidate.current_company || candidate.company || '').toLowerCase();
          const skills = (candidate.searchable_data?.skills_combined || candidate.primary_skills || []).join(' ').toLowerCase();
          const resumeText = (candidate.documents?.resume_text || '').toLowerCase();
          const location = (candidate.personal?.location || candidate.location || '').toLowerCase();

          // Use fuzzy matching for name (most likely to have typos)
          // Use exact contains for other fields for performance
          return fuzzyMatch(queryLower, name) ||
            fuzzyMatch(queryLower, title) ||
            fuzzyMatch(queryLower, company) ||
            skills.includes(queryLower) ||
            resumeText.includes(queryLower) ||
            location.includes(queryLower);
        });

        totalCount = filteredCandidates.length;

        // Apply pagination to filtered results
        const offset = (page - 1) * limit;
        candidates = filteredCandidates.slice(offset, offset + limit);
      } else {
        // No text search - use normal pagination
        const countSnapshot = await firestoreQuery.count().get();
        totalCount = countSnapshot.data().count;

        const offset = (page - 1) * limit;
        const resultsSnapshot = await firestoreQuery
          .offset(offset)
          .limit(limit)
          .get();

        candidates = resultsSnapshot.docs.map(doc => ({
          id: doc.id,
          ...doc.data(),
        }));
      }

      // Calculate pagination info
      const totalPages = Math.ceil(totalCount / limit);
      const hasNextPage = page < totalPages;
      const hasPreviousPage = page > 1;

      return {
        success: true,
        data: {
          candidates: candidates,
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
        created_at: admin.firestore.Timestamp.now(),
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

      console.log(`[getCandidateStats] User: ${userId}, Org: ${orgId}, Total Candidates: ${totalCandidates}`);

      // Fetch recent candidates for in-memory aggregation (more robust than count queries on missing fields)
      const recentDocsSnapshot = await candidatesRef
        .where('org_id', '==', orgId)
        .orderBy('created_at', 'desc')
        .limit(1000)
        .get();

      const experienceLevels: Record<string, number> = {
        'Entry': 0, 'Mid': 0, 'Senior': 0, 'Lead': 0, 'Executive': 0
      };

      const companyTiers: Record<string, number> = {
        'Tier 1': 0, 'High Growth': 0, 'Enterprise': 0, 'Startup': 0, 'Boutique': 0
      };

      const skillCounts: Record<string, number> = {};
      let processedCount = 0;
      let processedCandidates = 0; // To track candidates with local_analysis_completed

      recentDocsSnapshot.forEach(doc => {
        const data = doc.data();
        processedCount++;

        if (data.processing?.local_analysis_completed === true) {
          processedCandidates++;
        }

        // 1. Experience Level
        // Map 'Mid-Level' -> 'Mid', etc.
        let level = data.current_level || data.searchable_data?.experience_level || 'Unknown';
        if (level.includes('Entry') || level.includes('Junior')) level = 'Entry';
        else if (level.includes('Mid')) level = 'Mid';
        else if (level.includes('Senior')) level = 'Senior';
        else if (level.includes('Lead') || level.includes('Staff') || level.includes('Principal')) level = 'Lead';
        else if (level.includes('Executive') || level.includes('C-Level') || level.includes('VP') || level.includes('Director')) level = 'Executive';

        if (experienceLevels[level] !== undefined) {
          experienceLevels[level]++;
        }

        // 2. Company Pedigree
        // Fallback to 'Unknown' if missing
        const tier = data.analysis?.company_pedigree?.tier_level ||
          data.intelligent_analysis?.company_pedigree?.tier_level ||
          'Unknown';

        // Map raw tier values if needed
        let mappedTier = 'Unknown';
        if (tier.toLowerCase().includes('tier 1') || tier.toLowerCase().includes('faang')) mappedTier = 'Tier 1';
        else if (tier.toLowerCase().includes('high growth') || tier.toLowerCase().includes('unicorn')) mappedTier = 'High Growth';
        else if (tier.toLowerCase().includes('enterprise') || tier.toLowerCase().includes('fortune')) mappedTier = 'Enterprise';
        else if (tier.toLowerCase().includes('startup')) mappedTier = 'Startup';
        else if (tier.toLowerCase().includes('boutique')) mappedTier = 'Boutique';

        if (companyTiers[mappedTier] !== undefined) {
          companyTiers[mappedTier]++;
        }

        // 3. Skills
        const skills = data.all_probable_skills ||
          data.technical_skills ||
          data.intelligent_analysis?.explicit_skills?.technical_skills?.map((s: any) => s.skill) ||
          [];

        if (Array.isArray(skills)) {
          skills.forEach((skill: string) => {
            if (skill) {
              skillCounts[skill] = (skillCounts[skill] || 0) + 1;
            }
          });
        }
      });

      // Sort and get top skills
      const topSkills = Object.entries(skillCounts)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 20)
        .map(([skill, count]) => ({
          skill,
          count,
          percentage: Math.round((count / processedCount) * 100)
        }));

      // Calculate recent candidates (last 7 days)
      // We can do this from the fetched docs if they cover 7 days, or use a separate count query if volume is high.
      // For accuracy, let's keep the separate count query for "Recent" as it's cheap.
      const sevenDaysAgo = admin.firestore.Timestamp.fromMillis(Date.now() - 7 * 24 * 60 * 60 * 1000);
      const recentSnapshot = await candidatesRef
        .where('org_id', '==', orgId)
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
          experience_levels: experienceLevels,
          company_tiers: companyTiers,
          top_skills: topSkills,
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