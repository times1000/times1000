import { Request, Response, NextFunction } from 'express';

/**
 * Standard API error format
 */
export interface ApiError {
  error: string;
  details?: any;
  code?: string;
  status?: number;
}

/**
 * Creates a standardized API error
 */
export const createApiError = (
  message: string, 
  status = 500, 
  details?: any, 
  code?: string
): ApiError & { statusCode: number } => ({
  error: message,
  details,
  code,
  statusCode: status
});

/**
 * Global error handling middleware for Express routes
 */
export const errorMiddleware = (
  err: any, 
  _req: Request, 
  res: Response, 
  _next: NextFunction
) => {
  // Log the error
  console.error('API Error:', err instanceof Error ? err.stack : err);
  
  // Determine status code - use statusCode property if it exists, otherwise default to 500
  const statusCode = err.statusCode || 500;
  
  // Send back a proper error response
  res.status(statusCode).json({
    error: err.message || 'Internal Server Error',
    details: err.details,
    code: err.code,
    status: statusCode
  });
};

/**
 * Async handler to catch and forward errors to the error middleware
 */
export const asyncHandler = (fn: Function) => 
  (req: Request, res: Response, next: NextFunction) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };