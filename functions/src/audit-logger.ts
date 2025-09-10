/**
 * Audit logging service for tracking all system activities
 */

import * as admin from "firebase-admin";

export enum AuditAction {
  // Authentication
  USER_LOGIN = "USER_LOGIN",
  USER_LOGOUT = "USER_LOGOUT",
  AUTH_FAILED = "AUTH_FAILED",
  
  // Data Access
  DATA_READ = "DATA_READ",
  DATA_WRITE = "DATA_WRITE",
  DATA_DELETE = "DATA_DELETE",
  
  // Search Operations
  SEARCH_PERFORMED = "SEARCH_PERFORMED",
  SEMANTIC_SEARCH = "SEMANTIC_SEARCH",
  QUICK_MATCH = "QUICK_MATCH",
  
  // Profile Operations
  PROFILE_ENRICHED = "PROFILE_ENRICHED",
  EMBEDDING_GENERATED = "EMBEDDING_GENERATED",
  RESUME_PROCESSED = "RESUME_PROCESSED",
  
  // System Operations
  API_CALL = "API_CALL",
  ERROR_OCCURRED = "ERROR_OCCURRED",
  RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED",
  PERMISSION_DENIED = "PERMISSION_DENIED",
}

export interface AuditLog {
  timestamp: string;
  action: AuditAction;
  user_id?: string;
  user_email?: string;
  resource_type?: string;
  resource_id?: string;
  details?: any;
  ip_address?: string;
  user_agent?: string;
  success: boolean;
  error_message?: string;
  duration_ms?: number;
  metadata?: Record<string, any>;
}

export class AuditLogger {
  private static instance: AuditLogger;
  private firestore: admin.firestore.Firestore;
  private batchWriter: admin.firestore.WriteBatch | null = null;
  private batchCount: number = 0;
  private readonly BATCH_SIZE = 100;

  private constructor() {
    this.firestore = admin.firestore();
    
    // Flush batch periodically
    setInterval(() => this.flushBatch(), 5000);
  }

  static getInstance(): AuditLogger {
    if (!AuditLogger.instance) {
      AuditLogger.instance = new AuditLogger();
    }
    return AuditLogger.instance;
  }

  /**
   * Log an audit event
   */
  async log(
    action: AuditAction,
    options: {
      userId?: string;
      userEmail?: string;
      resourceType?: string;
      resourceId?: string;
      details?: any;
      ipAddress?: string;
      userAgent?: string;
      success?: boolean;
      errorMessage?: string;
      durationMs?: number;
      metadata?: Record<string, any>;
    } = {}
  ): Promise<void> {
    const auditLog: AuditLog = {
      timestamp: new Date().toISOString(),
      action,
      user_id: options.userId,
      user_email: options.userEmail,
      resource_type: options.resourceType,
      resource_id: options.resourceId,
      details: this.sanitizeDetails(options.details),
      ip_address: options.ipAddress,
      user_agent: options.userAgent,
      success: options.success !== false,
      error_message: options.errorMessage,
      duration_ms: options.durationMs,
      metadata: options.metadata,
    };

    try {
      // Add to batch for efficient writes
      await this.addToBatch(auditLog);
      
      // Also log to console for Cloud Logging
      console.log(`[AUDIT] ${action}`, {
        userId: options.userId,
        resourceId: options.resourceId,
        success: auditLog.success,
      });
    } catch (error) {
      console.error("Failed to write audit log:", error);
    }
  }

  /**
   * Add log to batch for efficient writing
   */
  private async addToBatch(auditLog: AuditLog): Promise<void> {
    if (!this.batchWriter) {
      this.batchWriter = this.firestore.batch();
    }

    const docRef = this.firestore.collection("audit_logs").doc();
    this.batchWriter.set(docRef, auditLog);
    this.batchCount++;

    // Flush if batch is full
    if (this.batchCount >= this.BATCH_SIZE) {
      await this.flushBatch();
    }
  }

  /**
   * Flush pending batch writes
   */
  async flushBatch(): Promise<void> {
    if (this.batchWriter && this.batchCount > 0) {
      try {
        await this.batchWriter.commit();
        console.log(`[AUDIT] Flushed ${this.batchCount} audit logs`);
      } catch (error) {
        console.error("Failed to flush audit batch:", error);
      } finally {
        this.batchWriter = null;
        this.batchCount = 0;
      }
    }
  }

  /**
   * Log a search operation
   */
  async logSearch(
    userId: string,
    searchType: "job_search" | "semantic" | "quick_match",
    query: any,
    resultCount: number,
    durationMs: number
  ): Promise<void> {
    await this.log(
      searchType === "semantic" ? AuditAction.SEMANTIC_SEARCH :
      searchType === "quick_match" ? AuditAction.QUICK_MATCH :
      AuditAction.SEARCH_PERFORMED,
      {
        userId,
        resourceType: "search",
        details: {
          search_type: searchType,
          query: this.sanitizeQuery(query),
          result_count: resultCount,
        },
        durationMs,
        success: true,
      }
    );
  }

  /**
   * Log an API call
   */
  async logApiCall(
    functionName: string,
    userId?: string,
    requestData?: any,
    responseStatus: "success" | "error" = "success",
    durationMs?: number
  ): Promise<void> {
    await this.log(AuditAction.API_CALL, {
      userId,
      resourceType: "function",
      resourceId: functionName,
      details: {
        request: this.sanitizeDetails(requestData),
        status: responseStatus,
      },
      success: responseStatus === "success",
      durationMs,
    });
  }

  /**
   * Log authentication events
   */
  async logAuth(
    action: "login" | "logout" | "failed",
    userId?: string,
    email?: string,
    reason?: string
  ): Promise<void> {
    const auditAction = 
      action === "login" ? AuditAction.USER_LOGIN :
      action === "logout" ? AuditAction.USER_LOGOUT :
      AuditAction.AUTH_FAILED;

    await this.log(auditAction, {
      userId,
      userEmail: email,
      errorMessage: reason,
      success: action !== "failed",
    });
  }

  /**
   * Query audit logs
   */
  async queryLogs(options: {
    userId?: string;
    action?: AuditAction;
    startDate?: Date;
    endDate?: Date;
    limit?: number;
  } = {}): Promise<AuditLog[]> {
    let query = this.firestore.collection("audit_logs")
      .orderBy("timestamp", "desc");

    if (options.userId) {
      query = query.where("user_id", "==", options.userId) as any;
    }

    if (options.action) {
      query = query.where("action", "==", options.action) as any;
    }

    if (options.startDate) {
      query = query.where("timestamp", ">=", options.startDate.toISOString()) as any;
    }

    if (options.endDate) {
      query = query.where("timestamp", "<=", options.endDate.toISOString()) as any;
    }

    query = query.limit(options.limit || 100) as any;

    const snapshot = await query.get();
    return snapshot.docs.map(doc => doc.data() as AuditLog);
  }

  /**
   * Generate audit report
   */
  async generateReport(
    startDate: Date,
    endDate: Date
  ): Promise<{
    total_events: number;
    events_by_action: Record<string, number>;
    events_by_user: Record<string, number>;
    error_rate: number;
    avg_duration_ms: number;
  }> {
    const logs = await this.queryLogs({
      startDate,
      endDate,
      limit: 10000,
    });

    const report = {
      total_events: logs.length,
      events_by_action: {} as Record<string, number>,
      events_by_user: {} as Record<string, number>,
      error_rate: 0,
      avg_duration_ms: 0,
    };

    let errorCount = 0;
    let totalDuration = 0;
    let durationCount = 0;

    for (const log of logs) {
      // Count by action
      report.events_by_action[log.action] = 
        (report.events_by_action[log.action] || 0) + 1;

      // Count by user
      if (log.user_id) {
        report.events_by_user[log.user_id] = 
          (report.events_by_user[log.user_id] || 0) + 1;
      }

      // Count errors
      if (!log.success) {
        errorCount++;
      }

      // Sum durations
      if (log.duration_ms) {
        totalDuration += log.duration_ms;
        durationCount++;
      }
    }

    report.error_rate = logs.length > 0 ? errorCount / logs.length : 0;
    report.avg_duration_ms = durationCount > 0 ? totalDuration / durationCount : 0;

    return report;
  }

  /**
   * Sanitize sensitive data from details
   */
  private sanitizeDetails(details: any): any {
    if (!details) return null;

    const sanitized = JSON.parse(JSON.stringify(details));
    const sensitiveKeys = [
      "password", "token", "api_key", "secret", 
      "credit_card", "ssn", "authorization"
    ];

    const sanitizeObject = (obj: any): any => {
      if (typeof obj !== "object" || obj === null) return obj;

      for (const key in obj) {
        if (sensitiveKeys.some(sensitive => 
          key.toLowerCase().includes(sensitive)
        )) {
          obj[key] = "[REDACTED]";
        } else if (typeof obj[key] === "object") {
          obj[key] = sanitizeObject(obj[key]);
        }
      }
      return obj;
    };

    return sanitizeObject(sanitized);
  }

  /**
   * Sanitize search query
   */
  private sanitizeQuery(query: any): any {
    if (typeof query === "string") {
      // Truncate long queries
      return query.length > 500 ? query.substring(0, 500) + "..." : query;
    }
    return this.sanitizeDetails(query);
  }

  /**
   * Clean up old audit logs
   */
  async cleanupOldLogs(daysToKeep: number = 90): Promise<number> {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - daysToKeep);

    const snapshot = await this.firestore
      .collection("audit_logs")
      .where("timestamp", "<", cutoffDate.toISOString())
      .get();

    let deletedCount = 0;
    const batch = this.firestore.batch();

    snapshot.docs.forEach((doc) => {
      batch.delete(doc.ref);
      deletedCount++;
    });

    if (deletedCount > 0) {
      await batch.commit();
      console.log(`[AUDIT] Cleaned up ${deletedCount} old audit logs`);
    }

    return deletedCount;
  }
}

// Export singleton instance
export const auditLogger = AuditLogger.getInstance();