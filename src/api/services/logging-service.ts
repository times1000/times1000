import db from '../../db';
import { v4 as uuidv4 } from 'uuid';

interface LogDetails {
  model?: string;
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

interface LogEntry extends LogDetails {
  id: string;
  timestamp: string;
  operation: string;
  loggingError?: string;
}

interface PaginationResult {
  logs: any[];
  pagination: {
    page: number;
    limit: number;
    totalItems: number;
    totalPages: number;
  };
}

/**
 * Log LLM API operation to database
 */
async function logOperation(operation: string, details: LogDetails): Promise<LogEntry> {
  try {
    const timestamp = new Date().toISOString();
    
    // Create log entry
    const logEntry: LogEntry = {
      id: uuidv4(),
      timestamp,
      operation,
      ...details
    };
    
    // Still log to console for debugging
    console.log(`[AI Operation Log] ${timestamp} - ${operation}:`, JSON.stringify({
      id: logEntry.id,
      operation,
      model: details.model,
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
    
    // Log more details before DB save
    console.log(`Saving log ${logEntry.id} to database with prompt length: ${promptToSave.length}, response length: ${responseToSave ? responseToSave.length : 0}`);
    
    // For debugging - log first 100 chars of prompt
    if (promptToSave) {
      console.log(`Prompt preview: ${promptToSave.substring(0, 100)}...`);
    }
    
    try {
      await db.llmLogs.createLog({
        id: logEntry.id,
        operation,
        model: details.model || 'unknown',
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
      console.log(`Successfully saved log ${logEntry.id} to database`);
    } catch (dbError: any) {
      console.error(`Database error saving log ${logEntry.id}:`, dbError);
      
      // Try one more time with minimal data
      try {
        console.log(`Retrying log ${logEntry.id} save with minimal data`);
        await db.llmLogs.createLog({
          id: logEntry.id,
          operation,
          model: details.model || 'unknown',
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
        console.log(`Successfully saved minimal log ${logEntry.id} to database`);
      } catch (retryError) {
        console.error(`Even minimal log ${logEntry.id} save failed:`, retryError);
      }
    }
    
    return logEntry;
  } catch (error: any) {
    console.error('Error in logging operation:', error);
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
 * Get all LLM API logs with pagination
 */
async function getLogs(page = 1, limit = 20): Promise<PaginationResult> {
  try {
    return await db.llmLogs.getLogs(page, limit);
  } catch (error) {
    console.error('Error fetching logs:', error);
    return {
      logs: [],
      pagination: { page, limit, totalItems: 0, totalPages: 0 }
    };
  }
}

/**
 * Get logs for a specific agent
 */
async function getLogsByAgentId(agentId: string, page = 1, limit = 20): Promise<PaginationResult> {
  try {
    return await db.llmLogs.getLogsByAgentId(agentId, page, limit);
  } catch (error) {
    console.error(`Error fetching logs for agent ${agentId}:`, error);
    return {
      logs: [],
      pagination: { page, limit, totalItems: 0, totalPages: 0 }
    };
  }
}

export {
  logOperation,
  getLogs,
  getLogsByAgentId
};