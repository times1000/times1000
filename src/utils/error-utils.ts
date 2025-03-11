/**
 * Utilities for standardized error handling across the application
 */

/**
 * Extract error message from different error types
 */
export const extractErrorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  } else if (typeof error === 'string') {
    return error;
  } else if (error && typeof error === 'object' && 'message' in error) {
    return String((error as any).message);
  }
  return 'Unknown error';
};

/**
 * Extract stack trace if available
 */
export const extractErrorStack = (error: unknown): string | undefined => {
  if (error instanceof Error) {
    return error.stack;
  } else if (error && typeof error === 'object' && 'stack' in error) {
    return String((error as any).stack);
  }
  return undefined;
};

/**
 * Log error with consistent format
 */
export const logError = (error: unknown, context: string): void => {
  const message = extractErrorMessage(error);
  const stack = extractErrorStack(error);
  
  console.error(`Error in ${context}: ${message}`);
  if (stack) {
    console.error(stack);
  }
};

/**
 * Create a detailed error object
 */
export interface DetailedError extends Error {
  code?: string;
  details?: any;
  statusCode?: number;
}

export const createError = (
  message: string, 
  code?: string, 
  details?: any, 
  statusCode?: number
): DetailedError => {
  const error = new Error(message) as DetailedError;
  if (code) error.code = code;
  if (details) error.details = details;
  if (statusCode) error.statusCode = statusCode;
  return error;
};

/**
 * Handle promise rejection with consistent pattern
 */
export const handleRejection = <T>(
  promise: Promise<T>, 
  context: string
): Promise<T> => {
  return promise.catch((error) => {
    logError(error, context);
    throw error;
  });
};