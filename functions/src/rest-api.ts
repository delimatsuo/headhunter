/**
 * RESTful API endpoints for Headhunter Cloud Functions
 * Comprehensive CRUD operations with authentication, validation, and CORS
 */

import { onRequest } from "firebase-functions/v2/https";
import { Request, Response } from "express";
import * as admin from "firebase-admin";
import { z } from "zod";
import cors from "cors";
import { VectorSearchService } from "./vector-search";

// Initialize services
const firestore = admin.firestore();
const vectorSearchService = new VectorSearchService();

// CORS configuration
const corsOptions = {
  origin: [
    'http://localhost:3000',
    'http://localhost:5000',
    'https://headhunter-app.web.app',
    'https://headhunter-app.firebaseapp.com'
  ],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['authorization', 'content-type', 'x-requested-with'],
  maxAge: 86400 // 24 hours
};

// Rate limiting store (simple in-memory for demo)
const rateLimitStore = new Map<string, { count: number; resetTime: number }>();

// Validation Schemas
const CandidateCreateSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email().optional(),
  phone: z.string().max(20).optional(),
  location: z.string().max(100).optional(),
  resume_text: z.string().optional(),
  notes: z.string().max(1000).optional(),
});

const CandidateUpdateSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  email: z.string().email().optional(),
  phone: z.string().max(20).optional(),
  location: z.string().max(100).optional(),
  notes: z.string().max(1000).optional(),
  status: z.enum(['active', 'interviewing', 'hired', 'rejected', 'withdrawn']).optional(),
});

const JobCreateSchema = z.object({
  title: z.string().min(1).max(200),
  company: z.string().min(1).max(100),
  description: z.string().max(5000),
  requirements: z.array(z.string().max(200)).optional(),
  location: z.string().max(100).optional(),
  salary_range: z.object({
    min: z.number().min(0).max(1000000),
    max: z.number().min(0).max(1000000)
  }).optional(),
  status: z.enum(['draft', 'active', 'paused', 'closed']).default('active')
});

const SemanticSearchSchema = z.object({
  query: z.string().min(1).max(500),
  filters: z.object({
    min_years_experience: z.number().min(0).max(50).optional(),
    current_level: z.string().optional(),
    company_tier: z.string().optional(),
    min_score: z.number().min(0).max(100).optional()
  }).optional(),
  limit: z.number().min(1).max(100).default(20)
});

// Types
interface AuthenticatedRequest extends Request {
  user?: {
    uid: string;
    org_id: string;
    permissions: Record<string, boolean>;
  };
}

interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  code?: string;
  details?: any;
  pagination?: {
    page: number;
    limit: number;
    total: number;
    has_next: boolean;
  };
  search_metadata?: {
    query: string;
    results_count: number;
    search_time_ms: number;
  };
  timestamp: string;
  request_id: string;
}

// Middleware Functions
function generateRequestId(): string {
  return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function authMiddleware(req: AuthenticatedRequest, res: Response, next: Function) {
  const requestId = generateRequestId();
  req.headers['x-request-id'] = requestId;

  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return sendError(res, 'Authorization header required', 'unauthenticated', 401, requestId);
  }

  const token = authHeader.substring(7);
  
  // Verify Firebase ID token
  admin.auth().verifyIdToken(token)
    .then(async (decodedToken) => {
      // Get user profile and organization info
      const userDoc = await firestore.collection('users').doc(decodedToken.uid).get();
      
      if (!userDoc.exists) {
        return sendError(res, 'User profile not found', 'not-found', 404, requestId);
      }

      const userData = userDoc.data()!;
      req.user = {
        uid: decodedToken.uid,
        org_id: userData.org_id || decodedToken.org_id,
        permissions: userData.permissions || {}
      };

      if (!req.user.org_id) {
        return sendError(res, 'Organization membership required', 'permission-denied', 403, requestId);
      }

      next();
    })
    .catch((error) => {
      console.error('Auth error:', error);
      return sendError(res, 'Invalid or expired token', 'unauthenticated', 401, requestId);
    });
}

function rateLimitMiddleware(req: AuthenticatedRequest, res: Response, next: Function) {
  const identifier = req.user?.uid || req.ip || 'anonymous';
  const now = Date.now();
  const windowSize = 60 * 1000; // 1 minute
  const maxRequests = 100;

  const userLimit = rateLimitStore.get(identifier);
  
  if (!userLimit || now > userLimit.resetTime) {
    // Reset or initialize
    rateLimitStore.set(identifier, { count: 1, resetTime: now + windowSize });
    return next();
  }

  if (userLimit.count >= maxRequests) {
    const retryAfter = Math.ceil((userLimit.resetTime - now) / 1000);
    res.set('Retry-After', retryAfter.toString());
    return sendError(res, 'Rate limit exceeded', 'too-many-requests', 429, 
                    req.headers['x-request-id'] as string, { retry_after: retryAfter });
  }

  userLimit.count++;
  next();
}

function permissionMiddleware(requiredPermission: string) {
  return (req: AuthenticatedRequest, res: Response, next: Function) => {
    if (!req.user?.permissions[requiredPermission]) {
      return sendError(res, 'Insufficient permissions', 'permission-denied', 403,
                      req.headers['x-request-id'] as string, 
                      { required_permission: requiredPermission });
    }
    next();
  };
}

// Utility Functions
function sendSuccess<T>(res: Response, data: T, requestId: string, pagination?: any, searchMetadata?: any): void {
  const response: ApiResponse<T> = {
    success: true,
    data,
    timestamp: new Date().toISOString(),
    request_id: requestId
  };

  if (pagination) {
    response.pagination = pagination;
  }

  if (searchMetadata) {
    response.search_metadata = searchMetadata;
  }

  res.status(200).json(response);
}

function sendError(res: Response, message: string, code: string, status: number, requestId: string, details?: any): void {
  const response: ApiResponse = {
    success: false,
    error: message,
    code,
    timestamp: new Date().toISOString(),
    request_id: requestId
  };

  if (details) {
    response.details = details;
  }

  // Log error for monitoring
  console.error(`Error [${requestId}]:`, { message, code, status, details });

  res.status(status).json(response);
}

function handleValidationError(error: z.ZodError, res: Response, requestId: string): void {
  const details = error.errors.map(err => ({
    field: err.path.join('.'),
    message: err.message,
    code: err.code
  }));

  sendError(res, 'Validation failed', 'invalid-argument', 400, requestId, details);
}

// Route Handlers
async function handleGetCandidates(req: AuthenticatedRequest, res: Response): Promise<void> {
  const requestId = req.headers['x-request-id'] as string;
  const orgId = req.user!.org_id;

  try {
    // Parse query parameters
    const page = parseInt(req.query.page as string) || 1;
    const limit = Math.min(parseInt(req.query.limit as string) || 20, 100);
    const offset = (page - 1) * limit;

    // Build query
    let query: admin.firestore.Query = firestore
      .collection('candidates')
      .where('org_id', '==', orgId)
      .where('deleted', '==', false);

    // Apply filters
    if (req.query.experience_level) {
      query = query.where('searchable_data.experience_level', '==', req.query.experience_level);
    }

    if (req.query.skills) {
      const skills = (req.query.skills as string).split(',');
      query = query.where('searchable_data.skills_combined', 'array-contains-any', skills);
    }

    if (req.query.location) {
      query = query.where('personal.location', '==', req.query.location);
    }

    // Apply sorting
    const sortField = req.query.sort_field as string || 'updated_at';
    const sortDirection = req.query.sort_direction === 'asc' ? 'asc' : 'desc';
    query = query.orderBy(sortField, sortDirection);

    // Get total count for pagination
    const totalSnapshot = await query.get();
    const total = totalSnapshot.size;

    // Apply pagination
    const snapshot = await query.offset(offset).limit(limit).get();
    
    const candidates = snapshot.docs.map(doc => ({
      candidate_id: doc.id,
      ...doc.data()
    }));

    const pagination = {
      page,
      limit,
      total,
      has_next: offset + limit < total
    };

    sendSuccess(res, candidates, requestId, pagination);
  } catch (error) {
    console.error('Error fetching candidates:', error);
    sendError(res, 'Failed to fetch candidates', 'internal', 500, requestId);
  }
}

async function handleCreateCandidate(req: AuthenticatedRequest, res: Response): Promise<void> {
  const requestId = req.headers['x-request-id'] as string;
  const orgId = req.user!.org_id;
  const userId = req.user!.uid;

  try {
    // Validate input
    const validatedData = CandidateCreateSchema.parse(req.body);

    const now = new Date().toISOString();
    const candidateData = {
      ...validatedData,
      org_id: orgId,
      created_by: userId,
      created_at: now,
      updated_at: now,
      status: 'active',
      deleted: false
    };

    // Create candidate
    const candidateRef = await firestore.collection('candidates').add(candidateData);

    // Return created candidate
    const candidate = {
      candidate_id: candidateRef.id,
      ...candidateData
    };

    sendSuccess(res, candidate, requestId);
  } catch (error) {
    if (error instanceof z.ZodError) {
      return handleValidationError(error, res, requestId);
    }
    
    console.error('Error creating candidate:', error);
    sendError(res, 'Failed to create candidate', 'internal', 500, requestId);
  }
}

async function handleUpdateCandidate(req: AuthenticatedRequest, res: Response): Promise<void> {
  const requestId = req.headers['x-request-id'] as string;
  const orgId = req.user!.org_id;
  const candidateId = req.params.id;

  try {
    // Validate input
    const validatedData = CandidateUpdateSchema.parse(req.body);

    // Check if candidate exists and belongs to organization
    const candidateRef = firestore.collection('candidates').doc(candidateId);
    const candidateDoc = await candidateRef.get();

    if (!candidateDoc.exists) {
      return sendError(res, 'Candidate not found', 'not-found', 404, requestId);
    }

    const candidateData = candidateDoc.data()!;
    if (candidateData.org_id !== orgId || candidateData.deleted) {
      return sendError(res, 'Candidate not found', 'not-found', 404, requestId);
    }

    // Update candidate
    const updateData = {
      ...validatedData,
      updated_at: new Date().toISOString()
    };

    await candidateRef.update(updateData);

    // Return updated candidate
    const updatedCandidate = {
      candidate_id: candidateId,
      ...candidateData,
      ...updateData
    };

    sendSuccess(res, updatedCandidate, requestId);
  } catch (error) {
    if (error instanceof z.ZodError) {
      return handleValidationError(error, res, requestId);
    }
    
    console.error('Error updating candidate:', error);
    sendError(res, 'Failed to update candidate', 'internal', 500, requestId);
  }
}

async function handleDeleteCandidate(req: AuthenticatedRequest, res: Response): Promise<void> {
  const requestId = req.headers['x-request-id'] as string;
  const orgId = req.user!.org_id;
  const candidateId = req.params.id;

  try {
    // Check if candidate exists and belongs to organization
    const candidateRef = firestore.collection('candidates').doc(candidateId);
    const candidateDoc = await candidateRef.get();

    if (!candidateDoc.exists) {
      return sendError(res, 'Candidate not found', 'not-found', 404, requestId);
    }

    const candidateData = candidateDoc.data()!;
    if (candidateData.org_id !== orgId || candidateData.deleted) {
      return sendError(res, 'Candidate not found', 'not-found', 404, requestId);
    }

    // Soft delete candidate
    const now = new Date().toISOString();
    await candidateRef.update({
      deleted: true,
      deleted_at: now,
      updated_at: now
    });

    sendSuccess(res, {
      candidate_id: candidateId,
      deleted: true,
      deleted_at: now
    }, requestId);
  } catch (error) {
    console.error('Error deleting candidate:', error);
    sendError(res, 'Failed to delete candidate', 'internal', 500, requestId);
  }
}

async function handleSemanticSearch(req: AuthenticatedRequest, res: Response): Promise<void> {
  const requestId = req.headers['x-request-id'] as string;
  const orgId = req.user!.org_id;

  try {
    // Validate input
    const searchParams = SemanticSearchSchema.parse(req.body);
    const startTime = Date.now();

    // Perform vector search
    const searchResults = await vectorSearchService.searchCandidates({
      query_text: searchParams.query,
      filters: searchParams.filters,
      limit: searchParams.limit,
      org_id: orgId
    });

    const searchTime = Date.now() - startTime;

    const searchMetadata = {
      query: searchParams.query,
      results_count: searchResults.length,
      search_time_ms: searchTime
    };

    sendSuccess(res, searchResults, requestId, undefined, searchMetadata);
  } catch (error) {
    if (error instanceof z.ZodError) {
      return handleValidationError(error, res, requestId);
    }
    
    console.error('Error performing semantic search:', error);
    sendError(res, 'Failed to perform search', 'internal', 500, requestId);
  }
}

async function handleSimilarCandidates(req: AuthenticatedRequest, res: Response): Promise<void> {
  const requestId = req.headers['x-request-id'] as string;
  const orgId = req.user!.org_id;
  const candidateId = req.params.id;

  try {
    const limit = Math.min(parseInt(req.query.limit as string) || 10, 50);

    // Check if reference candidate exists
    const candidateRef = firestore.collection('candidates').doc(candidateId);
    const candidateDoc = await candidateRef.get();

    if (!candidateDoc.exists) {
      return sendError(res, 'Candidate not found', 'not-found', 404, requestId);
    }

    const candidateData = candidateDoc.data()!;
    if (candidateData.org_id !== orgId || candidateData.deleted) {
      return sendError(res, 'Candidate not found', 'not-found', 404, requestId);
    }

    // Find similar candidates
    const similarResults = await vectorSearchService.findSimilarCandidates(candidateId, {
      limit,
      org_id: orgId
    });

    const response = {
      data: similarResults,
      reference_candidate: {
        candidate_id: candidateId,
        name: candidateData.name,
        current_level: candidateData.searchable_data?.experience_level
      }
    };

    sendSuccess(res, response, requestId);
  } catch (error) {
    console.error('Error finding similar candidates:', error);
    sendError(res, 'Failed to find similar candidates', 'internal', 500, requestId);
  }
}

// Main API Handler
async function apiHandler(req: Request, res: Response): Promise<void> {
  const method = req.method;
  const path = req.path;
  
  // Handle CORS preflight
  if (method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  // Route requests
  if (path.startsWith('/candidates')) {
    if (path === '/candidates' && method === 'GET') {
      await handleGetCandidates(req as AuthenticatedRequest, res);
    } else if (path === '/candidates' && method === 'POST') {
      await handleCreateCandidate(req as AuthenticatedRequest, res);
    } else if (path.match(/^\/candidates\/[^\/]+$/) && method === 'PUT') {
      req.params = { id: path.split('/')[2] };
      await handleUpdateCandidate(req as AuthenticatedRequest, res);
    } else if (path.match(/^\/candidates\/[^\/]+$/) && method === 'DELETE') {
      req.params = { id: path.split('/')[2] };
      await handleDeleteCandidate(req as AuthenticatedRequest, res);
    } else if (path.match(/^\/candidates\/[^\/]+\/similar$/) && method === 'GET') {
      req.params = { id: path.split('/')[2] };
      await handleSimilarCandidates(req as AuthenticatedRequest, res);
    } else {
      const requestId = generateRequestId();
      sendError(res, 'Endpoint not found', 'not-found', 404, requestId);
    }
  } else if (path.startsWith('/search')) {
    if (path === '/search/semantic' && method === 'POST') {
      await handleSemanticSearch(req as AuthenticatedRequest, res);
    } else {
      const requestId = generateRequestId();
      sendError(res, 'Endpoint not found', 'not-found', 404, requestId);
    }
  } else {
    const requestId = generateRequestId();
    sendError(res, 'Endpoint not found', 'not-found', 404, requestId);
  }
}

// Export Cloud Function
export const api = onRequest(
  {
    region: "us-central1",
    maxInstances: 10,
    memory: "512MiB",
    timeoutSeconds: 60
  },
  async (req: Request, res: Response) => {
    // Apply CORS
    cors(corsOptions)(req, res, async () => {
      // Apply middleware
      authMiddleware(req as AuthenticatedRequest, res, () => {
        rateLimitMiddleware(req as AuthenticatedRequest, res, () => {
          apiHandler(req, res);
        });
      });
    });
  }
);