/**
 * Centralized error handling for Cloud Functions
 */

import { HttpsError } from "firebase-functions/v2/https";
import * as admin from "firebase-admin";

interface ErrorLog {
  timestamp: string;
  function_name: string;
  error_type: string;
  error_message: string;
  stack_trace?: string;
  user_id?: string;
  request_data?: any;
  severity: "INFO" | "WARNING" | "ERROR" | "CRITICAL";
}

export class ErrorHandler {
  private static instance: ErrorHandler;
  private firestore: admin.firestore.Firestore;

  private constructor() {
    this.firestore = admin.firestore();
  }

  static getInstance(): ErrorHandler {
    if (!ErrorHandler.instance) {
      ErrorHandler.instance = new ErrorHandler();
    }
    return ErrorHandler.instance;
  }

  /**
   * Log error to Firestore for audit trail
   */
  async logError(
    functionName: string,
    error: any,
    userId?: string,
    requestData?: any
  ): Promise<void> {
    try {
      const errorLog: ErrorLog = {
        timestamp: new Date().toISOString(),
        function_name: functionName,
        error_type: error.name || "Unknown",
        error_message: error.message || "Unknown error",
        stack_trace: error.stack,
        user_id: userId,
        request_data: this.sanitizeRequestData(requestData),
        severity: this.determineSeverity(error),
      };

      // Store in Firestore audit log
      await this.firestore.collection("error_logs").add(errorLog);

      // Log to console for Cloud Logging
      console.error(`[${errorLog.severity}] ${functionName}:`, {
        message: error.message,
        stack: error.stack,
        userId,
      });
    } catch (logError) {
      // Fallback to console if logging fails
      console.error("Failed to log error:", logError);
      console.error("Original error:", error);
    }
  }

  /**
   * Handle error and return appropriate HttpsError
   */
  handleError(
    functionName: string,
    error: any,
    userId?: string,
    requestData?: any
  ): HttpsError {
    // Log the error
    this.logError(functionName, error, userId, requestData);

    // Determine appropriate error response
    if (error instanceof HttpsError) {
      return error;
    }

    // Handle specific error types
    if (error.code === "PERMISSION_DENIED") {
      return new HttpsError(
        "permission-denied",
        "You don't have permission to perform this action"
      );
    }

    if (error.code === "NOT_FOUND" || error.code === 404) {
      return new HttpsError(
        "not-found",
        "The requested resource was not found"
      );
    }

    if (error.code === "RESOURCE_EXHAUSTED") {
      return new HttpsError(
        "resource-exhausted",
        "Service temporarily unavailable due to high load"
      );
    }

    if (error.message?.includes("timeout")) {
      return new HttpsError(
        "deadline-exceeded",
        "Operation timed out. Please try again."
      );
    }

    if (error.message?.includes("memory")) {
      return new HttpsError(
        "resource-exhausted",
        "Insufficient resources to complete the operation"
      );
    }

    // Default error response
    return new HttpsError(
      "internal",
      "An unexpected error occurred. Please try again later."
    );
  }

  /**
   * Sanitize request data to avoid logging sensitive information
   */
  private sanitizeRequestData(data: any): any {
    if (!data) return null;

    const sanitized = { ...data };
    
    // Remove sensitive fields
    const sensitiveFields = [
      "password",
      "token",
      "api_key",
      "secret",
      "authorization",
      "credit_card",
      "ssn",
      "email",
      "phone",
    ];

    const removeSensitive = (obj: any): any => {
      if (typeof obj !== "object" || obj === null) return obj;

      const cleaned = Array.isArray(obj) ? [...obj] : { ...obj };

      for (const key in cleaned) {
        if (sensitiveFields.some(field => key.toLowerCase().includes(field))) {
          cleaned[key] = "[REDACTED]";
        } else if (typeof cleaned[key] === "object") {
          cleaned[key] = removeSensitive(cleaned[key]);
        }
      }

      return cleaned;
    };

    return removeSensitive(sanitized);
  }

  /**
   * Determine error severity
   */
  private determineSeverity(error: any): ErrorLog["severity"] {
    if (error instanceof HttpsError) {
      switch (error.code) {
        case "invalid-argument":
        case "not-found":
          return "INFO";
        case "permission-denied":
        case "unauthenticated":
          return "WARNING";
        case "resource-exhausted":
        case "deadline-exceeded":
          return "ERROR";
        default:
          return "ERROR";
      }
    }

    if (error.message?.includes("memory") || error.message?.includes("timeout")) {
      return "CRITICAL";
    }

    return "ERROR";
  }

  /**
   * Retry logic for transient failures
   */
  async retryOperation<T>(
    operation: () => Promise<T>,
    maxRetries: number = 3,
    delayMs: number = 1000
  ): Promise<T> {
    let lastError: any;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error: any) {
        lastError = error;
        
        // Don't retry on permanent failures
        if (
          error instanceof HttpsError &&
          ["invalid-argument", "permission-denied", "not-found"].includes(error.code)
        ) {
          throw error;
        }

        // Log retry attempt
        console.log(`Retry attempt ${attempt}/${maxRetries} after error:`, error.message);

        if (attempt < maxRetries) {
          // Exponential backoff
          await new Promise(resolve => setTimeout(resolve, delayMs * Math.pow(2, attempt - 1)));
        }
      }
    }

    throw lastError;
  }

  /**
   * Performance monitoring wrapper
   */
  async monitorPerformance<T>(
    functionName: string,
    operation: () => Promise<T>
  ): Promise<T> {
    const startTime = Date.now();
    
    try {
      const result = await operation();
      const duration = Date.now() - startTime;

      // Log slow operations
      if (duration > 5000) {
        console.warn(`Slow operation detected: ${functionName} took ${duration}ms`);
        
        await this.firestore.collection("performance_logs").add({
          timestamp: new Date().toISOString(),
          function_name: functionName,
          duration_ms: duration,
          status: "slow",
        });
      }

      return result;
    } catch (error) {
      const duration = Date.now() - startTime;
      
      await this.firestore.collection("performance_logs").add({
        timestamp: new Date().toISOString(),
        function_name: functionName,
        duration_ms: duration,
        status: "error",
        error_message: (error as any).message,
      });

      throw error;
    }
  }

  /**
   * Circuit breaker pattern for external services
   */
  private circuitBreakers = new Map<string, {
    failures: number;
    lastFailure: number;
    isOpen: boolean;
  }>();

  async withCircuitBreaker<T>(
    serviceName: string,
    operation: () => Promise<T>,
    options: {
      failureThreshold?: number;
      resetTimeMs?: number;
    } = {}
  ): Promise<T> {
    const { failureThreshold = 5, resetTimeMs = 60000 } = options;
    
    // Get or create circuit breaker state
    let breaker = this.circuitBreakers.get(serviceName);
    if (!breaker) {
      breaker = { failures: 0, lastFailure: 0, isOpen: false };
      this.circuitBreakers.set(serviceName, breaker);
    }

    // Check if circuit should be reset
    if (breaker.isOpen && Date.now() - breaker.lastFailure > resetTimeMs) {
      breaker.isOpen = false;
      breaker.failures = 0;
      console.log(`Circuit breaker reset for ${serviceName}`);
    }

    // Check if circuit is open
    if (breaker.isOpen) {
      throw new HttpsError(
        "unavailable",
        `Service ${serviceName} is temporarily unavailable`
      );
    }

    try {
      const result = await operation();
      
      // Reset failures on success
      if (breaker.failures > 0) {
        breaker.failures = 0;
        console.log(`Circuit breaker recovered for ${serviceName}`);
      }
      
      return result;
    } catch (error) {
      breaker.failures++;
      breaker.lastFailure = Date.now();

      if (breaker.failures >= failureThreshold) {
        breaker.isOpen = true;
        console.error(`Circuit breaker opened for ${serviceName} after ${breaker.failures} failures`);
      }

      throw error;
    }
  }
}

// Export singleton instance
export const errorHandler = ErrorHandler.getInstance();