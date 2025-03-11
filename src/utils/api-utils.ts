import { Response } from 'express';
import { API_RESPONSE } from '../config/constants';

/**
 * Standard success response interface
 */
export interface ApiSuccessResponse {
  success: boolean;
  data?: any;
  message?: string;
  [key: string]: any;
}

/**
 * Standard pagination response
 */
export interface PaginationMeta {
  page: number;
  limit: number;
  total?: number;
  totalPages?: number;
}

/**
 * Create standard success response
 */
export const createSuccessResponse = (
  data?: any,
  message?: string,
  additionalData?: Record<string, any>
): ApiSuccessResponse => {
  return {
    success: true,
    ...(data !== undefined && { data }),
    ...(message && { message }),
    ...additionalData
  };
};

/**
 * Send a standard success response
 */
export const sendSuccess = (
  res: Response,
  data?: any,
  message?: string,
  statusCode = 200,
  additionalData?: Record<string, any>
): Response => {
  return res.status(statusCode).json(
    createSuccessResponse(data, message, additionalData)
  );
};

/**
 * Send a standard created response (201)
 */
export const sendCreated = (
  res: Response,
  data?: any,
  message = 'Resource created successfully',
  additionalData?: Record<string, any>
): Response => {
  return sendSuccess(res, data, message, 201, additionalData);
};

/**
 * Send a standard paginated response
 */
export const sendPaginated = (
  res: Response,
  data: any[],
  pagination: PaginationMeta,
  message?: string,
  additionalData?: Record<string, any>
): Response => {
  return res.status(200).json({
    success: true,
    data,
    pagination,
    ...(message && { message }),
    ...additionalData
  });
};

/**
 * Send one of the predefined API responses from constants
 */
export const sendStandardResponse = (
  res: Response,
  responseType: keyof typeof API_RESPONSE,
  statusCode = 200
): Response => {
  return res.status(statusCode).json(API_RESPONSE[responseType]);
};