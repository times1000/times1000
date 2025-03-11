import db from '../../db';
import { v4 as uuidv4 } from 'uuid';

// Common interfaces for both log types
interface PaginationResult {
  logs: any[];
  pagination: {
    page: number;
    limit: number;
    totalItems: number;
    totalPages: number;
  };
}

// LLM log specific interfaces
interface LLMLogDetails {
  model?: string;
  provider?: string;
  prompt?: string;
  response?: string | null;
  tokensPrompt?: number;
  tokensCompletion?: number;
  durationMs?: number;
  costUsd?: number;
  status?: string;
  error?: string;
  agentId?: string | null;
  planId?: string | null;
  [key: string]: any;
}

interface LLMLogEntry extends LLMLogDetails {
  id: string;
  timestamp: string;
  operation: string;
  loggingError?: string;
}

// System log specific interfaces
interface SystemLogDetails {
  source: string;
  message?: string;
  details?: string;
  level?: 'info' | 'warning' | 'error' | 'debug';
  durationMs?: number;
  agentId?: string | null;
  planId?: string | null;
  [key: string]: any;
}

interface SystemLogEntry extends SystemLogDetails {
  id: string;
  timestamp: string;
  operation: string;
  loggingError?: string;
}

/**
 * Log LLM API operation to database
 */
async function logLLMOperation(operation: string, details: LLMLogDetails): Promise<LLMLogEntry> {
  try {
    const timestamp = new Date().toISOString();
    
    // Create log entry
    const logEntry: LLMLogEntry = {
      id: uuidv4(),
      timestamp,
      operation,
      ...details
    };
    
    // Still log to console for debugging
    console.log(`[LLM Operation Log] ${timestamp} - ${operation}:`, JSON.stringify({
      id: logEntry.id,
      operation,
      model: details.model,
      provider: details.provider,
      tokensPrompt: details.tokensPrompt,
      tokensCompletion: details.tokensCompletion,
      costUsd: details.costUsd,
      status: details.status
    }, null, 2));
    
    // Ensure we're saving data of appropriate lengths
    // Limit prompt/response to safe MySQL LONGTEXT limits (much shorter than actual limit for safety)
    const maxTextLength = 65000; // Safer limit for MySQL
    
    // Handle prompt - ensure it's a string
    let promptToSave = '';
    if (details.prompt) {
      if (typeof details.prompt === 'string') {
        promptToSave = details.prompt.length > maxTextLength ? 
          details.prompt.substring(0, maxTextLength) + '...(truncated)' : 
          details.prompt;
      } else {
        // If it's an object, stringify it
        try {
          const stringified = JSON.stringify(details.prompt);
          promptToSave = stringified.length > maxTextLength ? 
            stringified.substring(0, maxTextLength) + '...(truncated)' : 
            stringified;
        } catch (e) {
          console.error('Failed to stringify prompt:', e);
          promptToSave = 'Failed to stringify prompt data';
        }
      }
    }
    
    // Handle response - ensure it's a string or null
    let responseToSave = null;
    if (details.response) {
      if (typeof details.response === 'string') {
        responseToSave = details.response.length > maxTextLength ? 
          details.response.substring(0, maxTextLength) + '...(truncated)' : 
          details.response;
      } else {
        // If it's an object, stringify it
        try {
          const stringified = JSON.stringify(details.response);
          responseToSave = stringified.length > maxTextLength ? 
            stringified.substring(0, maxTextLength) + '...(truncated)' : 
            stringified;
        } catch (e) {
          console.error('Failed to stringify response:', e);
          responseToSave = 'Failed to stringify response data';
        }
      }
    }
    
    try {
      await db.llmLogs.createLog({
        id: logEntry.id,
        operation,
        model: details.model || 'unknown',
        provider: details.provider || 'unknown',
        prompt: promptToSave,
        response: responseToSave,
        tokensPrompt: details.tokensPrompt || 0,
        tokensCompletion: details.tokensCompletion || 0,
        costUsd: details.costUsd || null,
        durationMs: details.durationMs || 0,
        status: details.status || 'completed',
        errorMessage: details.error || null,
        agentId: details.agentId || null,
        planId: details.planId || null
      });
    } catch (dbError: any) {
      console.error(`Database error saving LLM log ${logEntry.id}:`, dbError);
      
      // Try one more time with minimal data
      try {
        await db.llmLogs.createLog({
          id: logEntry.id,
          operation,
          model: details.model || 'unknown',
          provider: details.provider || 'unknown',
          prompt: 'Log data too large - see console logs',
          response: null,
          tokensPrompt: details.tokensPrompt || 0,
          tokensCompletion: details.tokensCompletion || 0,
          costUsd: details.costUsd || null,
          durationMs: details.durationMs || 0,
          status: details.status || 'completed',
          errorMessage: `Original save failed: ${dbError.message}`,
          agentId: details.agentId || null,
          planId: details.planId || null
        });
      } catch (retryError) {
        console.error(`Even minimal LLM log ${logEntry.id} save failed:`, retryError);
      }
    }
    
    return logEntry;
  } catch (error: any) {
    console.error('Error in logging LLM operation:', error);
    // Still return something even if db save fails
    return {
      id: uuidv4(),
      timestamp: new Date().toISOString(),
      operation,
      ...details,
      loggingError: error.message
    };
  }
}

/**
 * Log system operation to database
 */
async function logSystemOperation(operation: string, details: SystemLogDetails): Promise<SystemLogEntry> {
  try {
    const timestamp = new Date().toISOString();
    
    // Create log entry
    const logEntry: SystemLogEntry = {
      id: uuidv4(),
      timestamp,
      operation,
      ...details
    };
    
    // Log to console for debugging
    console.log(`[System Log] ${timestamp} - ${details.source} - ${operation}:`, details.message);
    
    try {
      await db.logs.system.createLog({
        id: logEntry.id,
        source: details.source,
        operation,
        message: details.message || '',
        details: details.details || null,
        level: details.level || 'info',
        durationMs: details.durationMs || 0,
        agentId: details.agentId || null,
        planId: details.planId || null
      });
    } catch (dbError: any) {
      console.error(`Database error saving system log ${logEntry.id}:`, dbError);
    }
    
    return logEntry;
  } catch (error: any) {
    console.error('Error in logging system operation:', error);
    // Still return something even if db save fails
    return {
      id: uuidv4(),
      timestamp: new Date().toISOString(),
      operation,
      ...details,
      loggingError: error.message
    };
  }
}

/**
 * Legacy function for backward compatibility
 * Logs to the LLM table
 */
async function logOperation(operation: string, details: LLMLogDetails): Promise<LLMLogEntry> {
  return logLLMOperation(operation, details);
}

/**
 * Get all LLM logs with pagination
 */
async function getLLMLogs(page = 1, limit = 20): Promise<PaginationResult> {
  try {
    return await db.llmLogs.getLogs(page, limit);
  } catch (error) {
    console.error('Error fetching LLM logs:', error);
    return {
      logs: [],
      pagination: { page, limit, totalItems: 0, totalPages: 0 }
    };
  }
}

/**
 * Get all system logs with pagination
 */
async function getSystemLogs(page = 1, limit = 20): Promise<PaginationResult> {
  try {
    return await db.logs.system.getLogs(page, limit);
  } catch (error) {
    console.error('Error fetching system logs:', error);
    return {
      logs: [],
      pagination: { page, limit, totalItems: 0, totalPages: 0 }
    };
  }
}

/**
 * Get LLM logs for a specific agent
 */
async function getLLMLogsByAgentId(agentId: string, page = 1, limit = 20): Promise<PaginationResult> {
  try {
    return await db.llmLogs.getLogsByAgentId(agentId, page, limit);
  } catch (error) {
    console.error(`Error fetching LLM logs for agent ${agentId}:`, error);
    return {
      logs: [],
      pagination: { page, limit, totalItems: 0, totalPages: 0 }
    };
  }
}

/**
 * Get system logs for a specific agent
 */
async function getSystemLogsByAgentId(agentId: string, page = 1, limit = 20): Promise<PaginationResult> {
  try {
    return await db.logs.system.getLogsByAgentId(agentId, page, limit);
  } catch (error) {
    console.error(`Error fetching system logs for agent ${agentId}:`, error);
    return {
      logs: [],
      pagination: { page, limit, totalItems: 0, totalPages: 0 }
    };
  }
}

/**
 * Legacy functions for backward compatibility
 */
async function getLogs(page = 1, limit = 20): Promise<PaginationResult> {
  return getLLMLogs(page, limit);
}

async function getLogsByAgentId(agentId: string, page = 1, limit = 20): Promise<PaginationResult> {
  return getLLMLogsByAgentId(agentId, page, limit);
}

export {
  // New functions
  logLLMOperation,
  logSystemOperation,
  getLLMLogs,
  getSystemLogs,
  getLLMLogsByAgentId,
  getSystemLogsByAgentId,
  
  // Legacy functions for backward compatibility
  logOperation,
  getLogs,
  getLogsByAgentId
};