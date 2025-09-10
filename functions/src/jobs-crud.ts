#!/usr/bin/env node
/**
 * Jobs CRUD Operations
 * Complete create, read, update, delete operations for job management
 */

import { onCall, HttpsError } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";
import { z } from "zod";

// Initialize services
const firestore = admin.firestore();

// Validation Schemas
const CreateJobSchema = z.object({
  title: z.string().min(1).max(200),
  company: z.string().min(1).max(100),
  department: z.string().max(100).optional(),
  location: z.string().min(1).max(100),
  remote_policy: z.enum(['remote', 'hybrid', 'onsite']),
  employment_type: z.enum(['full-time', 'part-time', 'contract', 'internship']),
  seniority_level: z.enum(['entry', 'mid', 'senior', 'lead', 'executive']),
  
  // Description
  overview: z.string().min(10).max(5000),
  responsibilities: z.array(z.string().max(500)).min(1).max(20),
  required_skills: z.array(z.string().max(100)).min(1).max(30),
  preferred_skills: z.array(z.string().max(100)).max(30).optional(),
  
  // Experience requirements
  min_years_experience: z.number().min(0).max(50),
  max_years_experience: z.number().min(0).max(50).optional(),
  education_level: z.string().max(100).optional(),
  certifications: z.array(z.string().max(100)).max(10).optional(),
  
  // Compensation
  salary_min: z.number().min(0).max(10000000).optional(),
  salary_max: z.number().min(0).max(10000000).optional(),
  currency: z.string().length(3).optional(),
  benefits: z.array(z.string().max(100)).max(20).optional(),
  equity: z.boolean().optional(),
  
  // Team info
  team_size: z.number().min(0).max(10000).optional(),
  reporting_structure: z.string().max(500).optional(),
  work_culture: z.array(z.string().max(100)).max(10).optional(),
  
  // Job settings
  positions_available: z.number().min(1).max(100).default(1),
  urgency: z.enum(['low', 'medium', 'high']).default('medium'),
  deadline: z.string().datetime().optional(),
  
  // Matching criteria
  deal_breakers: z.array(z.string().max(200)).max(10).optional(),
  nice_to_haves: z.array(z.string().max(200)).max(10).optional(),
  cultural_fit_indicators: z.array(z.string().max(200)).max(10).optional(),
});

const UpdateJobSchema = z.object({
  title: z.string().min(1).max(200).optional(),
  company: z.string().min(1).max(100).optional(),
  department: z.string().max(100).optional(),
  location: z.string().min(1).max(100).optional(),
  remote_policy: z.enum(['remote', 'hybrid', 'onsite']).optional(),
  employment_type: z.enum(['full-time', 'part-time', 'contract', 'internship']).optional(),
  seniority_level: z.enum(['entry', 'mid', 'senior', 'lead', 'executive']).optional(),
  
  overview: z.string().min(10).max(5000).optional(),
  responsibilities: z.array(z.string().max(500)).min(1).max(20).optional(),
  required_skills: z.array(z.string().max(100)).min(1).max(30).optional(),
  preferred_skills: z.array(z.string().max(100)).max(30).optional(),
  
  min_years_experience: z.number().min(0).max(50).optional(),
  max_years_experience: z.number().min(0).max(50).optional(),
  education_level: z.string().max(100).optional(),
  certifications: z.array(z.string().max(100)).max(10).optional(),
  
  salary_min: z.number().min(0).max(10000000).optional(),
  salary_max: z.number().min(0).max(10000000).optional(),
  currency: z.string().length(3).optional(),
  benefits: z.array(z.string().max(100)).max(20).optional(),
  equity: z.boolean().optional(),
  
  team_size: z.number().min(0).max(10000).optional(),
  reporting_structure: z.string().max(500).optional(),
  work_culture: z.array(z.string().max(100)).max(10).optional(),
  
  positions_available: z.number().min(1).max(100).optional(),
  urgency: z.enum(['low', 'medium', 'high']).optional(),
  deadline: z.string().datetime().optional(),
  is_active: z.boolean().optional(),
  applications_open: z.boolean().optional(),
  
  deal_breakers: z.array(z.string().max(200)).max(10).optional(),
  nice_to_haves: z.array(z.string().max(200)).max(10).optional(),
  cultural_fit_indicators: z.array(z.string().max(200)).max(10).optional(),
});

const SearchJobsSchema = z.object({
  query: z.string().max(500).optional(),
  filters: z.object({
    company: z.string().optional(),
    location: z.string().optional(),
    remote_policy: z.enum(['remote', 'hybrid', 'onsite']).optional(),
    employment_type: z.enum(['full-time', 'part-time', 'contract', 'internship']).optional(),
    seniority_level: z.enum(['entry', 'mid', 'senior', 'lead', 'executive']).optional(),
    min_salary: z.number().min(0).optional(),
    max_salary: z.number().min(0).optional(),
    is_active: z.boolean().optional(),
    urgency: z.enum(['low', 'medium', 'high']).optional(),
    has_equity: z.boolean().optional(),
  }).optional(),
  sort: z.object({
    field: z.enum(['created_at', 'updated_at', 'title', 'company', 'deadline', 'urgency']),
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

function buildJobSearchQuery(orgId: string, filters: any = {}, sort: any = {}) {
  let query: admin.firestore.Query = firestore
    .collection('jobs')
    .where('org_id', '==', orgId);

  // Apply filters
  if (filters.company) {
    query = query.where('details.company', '==', filters.company);
  }

  if (filters.location) {
    query = query.where('details.location', '==', filters.location);
  }

  if (filters.remote_policy) {
    query = query.where('details.remote_policy', '==', filters.remote_policy);
  }

  if (filters.employment_type) {
    query = query.where('details.employment_type', '==', filters.employment_type);
  }

  if (filters.seniority_level) {
    query = query.where('details.seniority_level', '==', filters.seniority_level);
  }

  if (filters.is_active !== undefined) {
    query = query.where('status.is_active', '==', filters.is_active);
  }

  if (filters.urgency) {
    query = query.where('status.urgency', '==', filters.urgency);
  }

  // Apply sorting
  const sortField = sort.field || 'updated_at';
  const sortDirection = sort.direction || 'desc';
  query = query.orderBy(sortField, sortDirection);

  return query;
}

/**
 * Create a new job posting
 */
export const createJob = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);
    
    // Check permissions
    const canCreate = await validatePermissions(userId, 'can_create_jobs');
    if (!canCreate) {
      throw new HttpsError("permission-denied", "Insufficient permissions to create jobs");
    }

    // Validate input
    let validatedInput;
    try {
      validatedInput = CreateJobSchema.parse(request.data);
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
      }
      throw new HttpsError("invalid-argument", "Invalid request data");
    }

    try {
      const jobId = firestore.collection('jobs').doc().id;
      
      const jobData = {
        job_id: jobId,
        org_id: orgId,
        created_by: userId,
        created_at: admin.firestore.FieldValue.serverTimestamp(),
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
        
        // Job Details
        details: {
          title: validatedInput.title,
          company: validatedInput.company,
          department: validatedInput.department || null,
          location: validatedInput.location,
          remote_policy: validatedInput.remote_policy,
          employment_type: validatedInput.employment_type,
          seniority_level: validatedInput.seniority_level,
        },
        
        // Job Description
        description: {
          overview: validatedInput.overview,
          responsibilities: validatedInput.responsibilities,
          requirements: {
            required_skills: validatedInput.required_skills,
            preferred_skills: validatedInput.preferred_skills || [],
            years_experience: {
              min: validatedInput.min_years_experience,
              max: validatedInput.max_years_experience || null,
            },
            education_level: validatedInput.education_level || null,
            certifications: validatedInput.certifications || [],
          },
          compensation: {
            salary_range: (validatedInput.salary_min || validatedInput.salary_max) ? {
              min: validatedInput.salary_min || 0,
              max: validatedInput.salary_max || 0,
              currency: validatedInput.currency || 'USD',
            } : null,
            benefits: validatedInput.benefits || [],
            equity: validatedInput.equity || false,
          },
        },
        
        // Team & Culture
        team_info: {
          team_size: validatedInput.team_size || null,
          reporting_structure: validatedInput.reporting_structure || null,
          work_culture: validatedInput.work_culture || [],
          growth_opportunities: [],
        },
        
        // Job Status
        status: {
          is_active: true,
          applications_open: true,
          urgency: validatedInput.urgency,
          positions_available: validatedInput.positions_available,
          deadline: validatedInput.deadline ? new Date(validatedInput.deadline) : null,
        },
        
        // Search & Matching
        matching_criteria: {
          deal_breakers: validatedInput.deal_breakers || [],
          nice_to_haves: validatedInput.nice_to_haves || [],
          cultural_fit_indicators: validatedInput.cultural_fit_indicators || [],
          personality_traits: [],
        },
        
        // Analytics
        analytics: {
          views: 0,
          applications: 0,
          matches_generated: 0,
          avg_candidate_score: 0,
        },
      };

      await firestore.collection('jobs').doc(jobId).set(jobData);

      return {
        success: true,
        job_id: jobId,
        data: jobData,
      };
    } catch (error) {
      console.error("Error creating job:", error);
      throw new HttpsError("internal", "Failed to create job");
    }
  }
);

/**
 * Get a single job by ID
 */
export const getJob = onCall(
  {
    memory: "256MiB",
    timeoutSeconds: 30,
  },
  async (request) => {
    const { orgId } = validateAuth(request);
    const { job_id } = request.data;

    if (!job_id) {
      throw new HttpsError("invalid-argument", "Job ID is required");
    }

    try {
      const jobDoc = await firestore.collection('jobs').doc(job_id).get();

      if (!jobDoc.exists) {
        throw new HttpsError("not-found", "Job not found");
      }

      const jobData = jobDoc.data();
      
      // Check organization access
      if (jobData?.org_id !== orgId) {
        throw new HttpsError("permission-denied", "Access denied to this job");
      }

      // Increment view count
      await jobDoc.ref.update({
        'analytics.views': admin.firestore.FieldValue.increment(1),
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
      });

      return {
        success: true,
        data: jobData,
      };
    } catch (error) {
      if (error instanceof HttpsError) throw error;
      console.error("Error getting job:", error);
      throw new HttpsError("internal", "Failed to retrieve job");
    }
  }
);

/**
 * Update an existing job
 */
export const updateJob = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);
    const { job_id, ...updateData } = request.data;

    if (!job_id) {
      throw new HttpsError("invalid-argument", "Job ID is required");
    }

    // Check permissions
    const canEdit = await validatePermissions(userId, 'can_create_jobs'); // Same permission for edit
    if (!canEdit) {
      throw new HttpsError("permission-denied", "Insufficient permissions to edit jobs");
    }

    // Validate input
    let validatedInput;
    try {
      validatedInput = UpdateJobSchema.parse(updateData);
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new HttpsError("invalid-argument", `Invalid input: ${error.errors[0].message}`);
      }
      throw new HttpsError("invalid-argument", "Invalid request data");
    }

    try {
      const jobDoc = await firestore.collection('jobs').doc(job_id).get();

      if (!jobDoc.exists) {
        throw new HttpsError("not-found", "Job not found");
      }

      const existingData = jobDoc.data();
      
      // Check organization access
      if (existingData?.org_id !== orgId) {
        throw new HttpsError("permission-denied", "Access denied to this job");
      }

      // Build update object
      const updateObj: any = {
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
      };

      // Update job details
      if (validatedInput.title) updateObj['details.title'] = validatedInput.title;
      if (validatedInput.company) updateObj['details.company'] = validatedInput.company;
      if (validatedInput.department !== undefined) updateObj['details.department'] = validatedInput.department;
      if (validatedInput.location) updateObj['details.location'] = validatedInput.location;
      if (validatedInput.remote_policy) updateObj['details.remote_policy'] = validatedInput.remote_policy;
      if (validatedInput.employment_type) updateObj['details.employment_type'] = validatedInput.employment_type;
      if (validatedInput.seniority_level) updateObj['details.seniority_level'] = validatedInput.seniority_level;

      // Update description
      if (validatedInput.overview) updateObj['description.overview'] = validatedInput.overview;
      if (validatedInput.responsibilities) updateObj['description.responsibilities'] = validatedInput.responsibilities;
      if (validatedInput.required_skills) updateObj['description.requirements.required_skills'] = validatedInput.required_skills;
      if (validatedInput.preferred_skills) updateObj['description.requirements.preferred_skills'] = validatedInput.preferred_skills;
      
      // Update experience requirements
      if (validatedInput.min_years_experience !== undefined) {
        updateObj['description.requirements.years_experience.min'] = validatedInput.min_years_experience;
      }
      if (validatedInput.max_years_experience !== undefined) {
        updateObj['description.requirements.years_experience.max'] = validatedInput.max_years_experience;
      }
      if (validatedInput.education_level !== undefined) {
        updateObj['description.requirements.education_level'] = validatedInput.education_level;
      }
      if (validatedInput.certifications) {
        updateObj['description.requirements.certifications'] = validatedInput.certifications;
      }

      // Update compensation
      if (validatedInput.salary_min !== undefined || validatedInput.salary_max !== undefined) {
        const currentCompensation = existingData?.description?.compensation || {};
        const currentSalaryRange = currentCompensation.salary_range || {};
        
        updateObj['description.compensation.salary_range'] = {
          min: validatedInput.salary_min ?? currentSalaryRange.min ?? 0,
          max: validatedInput.salary_max ?? currentSalaryRange.max ?? 0,
          currency: validatedInput.currency ?? currentSalaryRange.currency ?? 'USD',
        };
      }
      if (validatedInput.benefits) updateObj['description.compensation.benefits'] = validatedInput.benefits;
      if (validatedInput.equity !== undefined) updateObj['description.compensation.equity'] = validatedInput.equity;

      // Update team info
      if (validatedInput.team_size !== undefined) updateObj['team_info.team_size'] = validatedInput.team_size;
      if (validatedInput.reporting_structure !== undefined) updateObj['team_info.reporting_structure'] = validatedInput.reporting_structure;
      if (validatedInput.work_culture) updateObj['team_info.work_culture'] = validatedInput.work_culture;

      // Update status
      if (validatedInput.positions_available) updateObj['status.positions_available'] = validatedInput.positions_available;
      if (validatedInput.urgency) updateObj['status.urgency'] = validatedInput.urgency;
      if (validatedInput.deadline !== undefined) {
        updateObj['status.deadline'] = validatedInput.deadline ? new Date(validatedInput.deadline) : null;
      }
      if (validatedInput.is_active !== undefined) updateObj['status.is_active'] = validatedInput.is_active;
      if (validatedInput.applications_open !== undefined) updateObj['status.applications_open'] = validatedInput.applications_open;

      // Update matching criteria
      if (validatedInput.deal_breakers) updateObj['matching_criteria.deal_breakers'] = validatedInput.deal_breakers;
      if (validatedInput.nice_to_haves) updateObj['matching_criteria.nice_to_haves'] = validatedInput.nice_to_haves;
      if (validatedInput.cultural_fit_indicators) updateObj['matching_criteria.cultural_fit_indicators'] = validatedInput.cultural_fit_indicators;

      await jobDoc.ref.update(updateObj);

      // Get updated document
      const updatedDoc = await jobDoc.ref.get();

      return {
        success: true,
        data: updatedDoc.data(),
      };
    } catch (error) {
      if (error instanceof HttpsError) throw error;
      console.error("Error updating job:", error);
      throw new HttpsError("internal", "Failed to update job");
    }
  }
);

/**
 * Delete a job
 */
export const deleteJob = onCall(
  {
    memory: "256MiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);
    const { job_id } = request.data;

    if (!job_id) {
      throw new HttpsError("invalid-argument", "Job ID is required");
    }

    // Check permissions
    const canEdit = await validatePermissions(userId, 'can_create_jobs');
    if (!canEdit) {
      throw new HttpsError("permission-denied", "Insufficient permissions to delete jobs");
    }

    try {
      const jobDoc = await firestore.collection('jobs').doc(job_id).get();

      if (!jobDoc.exists) {
        throw new HttpsError("not-found", "Job not found");
      }

      const jobData = jobDoc.data();
      
      // Check organization access
      if (jobData?.org_id !== orgId) {
        throw new HttpsError("permission-denied", "Access denied to this job");
      }

      // Use batch for atomic deletion
      const batch = firestore.batch();

      // Delete job document
      batch.delete(jobDoc.ref);

      // Clean up related search cache entries
      const searchCacheQuery = await firestore
        .collection('search_cache')
        .where('job_id', '==', job_id)
        .get();

      searchCacheQuery.docs.forEach(doc => {
        batch.delete(doc.ref);
      });

      await batch.commit();

      return {
        success: true,
        job_id: job_id,
      };
    } catch (error) {
      if (error instanceof HttpsError) throw error;
      console.error("Error deleting job:", error);
      throw new HttpsError("internal", "Failed to delete job");
    }
  }
);

/**
 * Search jobs with advanced filtering
 */
export const searchJobs = onCall(
  {
    memory: "1GiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);

    // Check permissions
    const canView = await validatePermissions(userId, 'can_view_candidates'); // Basic view permission
    if (!canView) {
      throw new HttpsError("permission-denied", "Insufficient permissions to view jobs");
    }

    // Validate input
    let validatedInput;
    try {
      validatedInput = SearchJobsSchema.parse(request.data);
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
      let firestoreQuery = buildJobSearchQuery(orgId, filters, sort);

      // Get total count for pagination
      const countSnapshot = await firestoreQuery.count().get();
      const totalCount = countSnapshot.data().count;

      // Apply pagination
      const resultsSnapshot = await firestoreQuery
        .offset(offset)
        .limit(limit)
        .get();

      const jobs = resultsSnapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data(),
      }));

      // If text query provided, perform additional filtering
      let filteredJobs = jobs;
      if (searchQuery && searchQuery.trim()) {
        const queryLower = searchQuery.toLowerCase();
        filteredJobs = jobs.filter((job: any) => {
          const title = job.details?.title?.toLowerCase() || '';
          const company = job.details?.company?.toLowerCase() || '';
          const overview = job.description?.overview?.toLowerCase() || '';
          const skills = (job.description?.requirements?.required_skills || []).join(' ').toLowerCase();
          const location = job.details?.location?.toLowerCase() || '';
          
          return title.includes(queryLower) || 
                 company.includes(queryLower) || 
                 overview.includes(queryLower) ||
                 skills.includes(queryLower) ||
                 location.includes(queryLower);
        });
      }

      // Apply salary filtering if needed
      if (filters?.min_salary || filters?.max_salary) {
        filteredJobs = filteredJobs.filter((job: any) => {
          const salaryRange = job.description?.compensation?.salary_range;
          if (!salaryRange) return true; // Include jobs without salary info
          
          const jobMinSalary = salaryRange.min || 0;
          const jobMaxSalary = salaryRange.max || 999999999;
          
          if (filters.min_salary && jobMaxSalary < filters.min_salary) return false;
          if (filters.max_salary && jobMinSalary > filters.max_salary) return false;
          
          return true;
        });
      }

      // Calculate pagination info
      const totalPages = Math.ceil(totalCount / limit);
      const hasNextPage = page < totalPages;
      const hasPreviousPage = page > 1;

      return {
        success: true,
        data: {
          jobs: filteredJobs,
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
      console.error("Error searching jobs:", error);
      throw new HttpsError("internal", "Failed to search jobs");
    }
  }
);

/**
 * Get jobs list with pagination
 */
export const getJobs = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 30,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);

    // Check permissions
    const canView = await validatePermissions(userId, 'can_view_candidates');
    if (!canView) {
      throw new HttpsError("permission-denied", "Insufficient permissions to view jobs");
    }

    const { page = 1, limit = 20, sort_by = 'updated_at', sort_order = 'desc', active_only = true } = request.data;

    try {
      const offset = (page - 1) * limit;

      let query = firestore.collection('jobs').where('org_id', '==', orgId);
      
      if (active_only) {
        query = query.where('status.is_active', '==', true);
      }

      // Get total count
      const countSnapshot = await query.count().get();
      const totalCount = countSnapshot.data().count;

      // Get paginated results
      const jobsSnapshot = await query
        .orderBy(sort_by, sort_order as any)
        .offset(offset)
        .limit(limit)
        .get();

      const jobs = jobsSnapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data(),
      }));

      const totalPages = Math.ceil(totalCount / limit);

      return {
        success: true,
        data: {
          jobs,
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
      console.error("Error getting jobs:", error);
      throw new HttpsError("internal", "Failed to retrieve jobs");
    }
  }
);

/**
 * Duplicate an existing job
 */
export const duplicateJob = onCall(
  {
    memory: "512MiB",
    timeoutSeconds: 60,
  },
  async (request) => {
    const { userId, orgId } = validateAuth(request);
    const { job_id } = request.data;

    if (!job_id) {
      throw new HttpsError("invalid-argument", "Job ID is required");
    }

    // Check permissions
    const canCreate = await validatePermissions(userId, 'can_create_jobs');
    if (!canCreate) {
      throw new HttpsError("permission-denied", "Insufficient permissions to create jobs");
    }

    try {
      const originalJobDoc = await firestore.collection('jobs').doc(job_id).get();

      if (!originalJobDoc.exists) {
        throw new HttpsError("not-found", "Original job not found");
      }

      const originalJobData = originalJobDoc.data();
      
      // Check organization access
      if (originalJobData?.org_id !== orgId) {
        throw new HttpsError("permission-denied", "Access denied to this job");
      }

      // Create new job with duplicated data
      const newJobId = firestore.collection('jobs').doc().id;
      
      const duplicatedJobData = {
        ...originalJobData,
        job_id: newJobId,
        created_by: userId,
        created_at: admin.firestore.FieldValue.serverTimestamp(),
        updated_at: admin.firestore.FieldValue.serverTimestamp(),
        
        // Modify title to indicate it's a copy
        details: {
          ...originalJobData.details,
          title: `${originalJobData.details.title} (Copy)`,
        },
        
        // Reset analytics
        analytics: {
          views: 0,
          applications: 0,
          matches_generated: 0,
          avg_candidate_score: 0,
        },
        
        // Reset status to active
        status: {
          ...originalJobData.status,
          is_active: true,
          applications_open: true,
        },
      };

      await firestore.collection('jobs').doc(newJobId).set(duplicatedJobData);

      return {
        success: true,
        job_id: newJobId,
        original_job_id: job_id,
        data: duplicatedJobData,
      };
    } catch (error) {
      if (error instanceof HttpsError) throw error;
      console.error("Error duplicating job:", error);
      throw new HttpsError("internal", "Failed to duplicate job");
    }
  }
);

/**
 * Get job statistics for dashboard
 */
export const getJobStats = onCall(
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
      const jobsRef = firestore.collection('jobs').where('org_id', '==', orgId);

      // Get total count
      const totalSnapshot = await jobsRef.count().get();
      const totalJobs = totalSnapshot.data().count;

      // Get active jobs count
      const activeSnapshot = await jobsRef
        .where('status.is_active', '==', true)
        .count()
        .get();
      const activeJobs = activeSnapshot.data().count;

      // Get urgent jobs count
      const urgentSnapshot = await jobsRef
        .where('status.urgency', '==', 'high')
        .where('status.is_active', '==', true)
        .count()
        .get();
      const urgentJobs = urgentSnapshot.data().count;

      // Get jobs by seniority level
      const seniorityLevels = ['entry', 'mid', 'senior', 'lead', 'executive'];
      const seniorityStats: { [key: string]: number } = {};
      
      for (const level of seniorityLevels) {
        const snapshot = await jobsRef
          .where('details.seniority_level', '==', level)
          .where('status.is_active', '==', true)
          .count()
          .get();
        seniorityStats[level] = snapshot.data().count;
      }

      // Get jobs by employment type
      const employmentTypes = ['full-time', 'part-time', 'contract', 'internship'];
      const employmentStats: { [key: string]: number } = {};
      
      for (const type of employmentTypes) {
        const snapshot = await jobsRef
          .where('details.employment_type', '==', type)
          .where('status.is_active', '==', true)
          .count()
          .get();
        employmentStats[type] = snapshot.data().count;
      }

      // Get recent activity (last 7 days)
      const sevenDaysAgo = new Date();
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
      
      const recentSnapshot = await jobsRef
        .where('created_at', '>=', sevenDaysAgo)
        .count()
        .get();
      const recentJobs = recentSnapshot.data().count;

      return {
        success: true,
        stats: {
          total_jobs: totalJobs,
          active_jobs: activeJobs,
          inactive_jobs: totalJobs - activeJobs,
          urgent_jobs: urgentJobs,
          recent_jobs: recentJobs,
          seniority_levels: seniorityStats,
          employment_types: employmentStats,
          job_activation_rate: totalJobs > 0 
            ? Math.round((activeJobs / totalJobs) * 100) 
            : 0,
        },
      };
    } catch (error) {
      console.error("Error getting job stats:", error);
      throw new HttpsError("internal", "Failed to retrieve statistics");
    }
  }
);