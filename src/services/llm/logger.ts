import db from '../../db';
// Force reload db to ensure fresh connection
db.testConnection();
import { v4 as uuidv4 } from 'uuid';
import { LLMMessage, TokenUsage, RequestContext } from './types';

/**
 * LLM Request Logger - Logs all LLM API calls to database
 */
export async function logLLMRequest({
  provider,
  model,
  operation,
  prompt,
  response,
  tokenUsage,
  costUsd,
  durationMs,
  status = 'completed',
  error = null,
  context = {}
}: {
  provider: string;
  model: string;
  operation: string;
  prompt: LLMMessage[] | string;
  response?: string | null;
  tokenUsage: TokenUsage;
  costUsd: number;
  durationMs: number;
  status?: string;
  error?: string | null;
  context?: RequestContext;
}): Promise<void> {
  try {
    const id = uuidv4();
    const timestamp = new Date().toISOString();
    
    // Prepare prompt for storage
    const promptString = typeof prompt === 'string' 
      ? prompt 
      : JSON.stringify(prompt);
    
    // Log to console for debugging (minimal details)
    console.log(`[LLM ${provider}] ${timestamp} - ${operation}:`, {
      id,
      model,
      provider,
      tokens: {
        prompt: tokenUsage.promptTokens,
        completion: tokenUsage.completionTokens,
        total: tokenUsage.totalTokens
      },
      costUsd,
      status,
      agentId: context.agentId,
      planId: context.planId
    });
    
    // Ensure text lengths are appropriate for database
    const maxTextLength = 65000; // Safe limit for MySQL LONGTEXT
    
    // Truncate prompt if needed
    const promptToSave = promptString.length > maxTextLength
      ? promptString.substring(0, maxTextLength) + '...(truncated)'
      : promptString;
    
    // Handle response - ensure it's a string or null
    let responseToSave = null;
    if (response) {
      responseToSave = response.length > maxTextLength
        ? response.substring(0, maxTextLength) + '...(truncated)'
        : response;
    }
    
    // Save to database
    try {
      // Check if agent exists before attempting to log
      // This avoids foreign key constraint errors when the agent is not yet created
      let safeAgentId = null;
      if (context.agentId) {
        try {
          const agent = await db.agents.getAgentById(context.agentId);
          if (agent) {
            safeAgentId = context.agentId;
          }
        } catch (err) {
          console.log(`Agent ${context.agentId} not found in database, logging without agentId reference`);
        }
      }
      
      await db.llmLogs.createLog({
        id,
        operation,
        model,
        prompt: promptToSave,
        response: responseToSave,
        tokensPrompt: tokenUsage.promptTokens,
        tokensCompletion: tokenUsage.completionTokens,
        costUsd,
        durationMs,
        status,
        errorMessage: error,
        agentId: safeAgentId,
        planId: context.planId || null
      });
    } catch (dbError: any) {
      console.error('Error saving LLM log to database:', dbError);
      
      // Try one more time with minimal data
      try {
        // Even for fallback, we need to be safe about foreign keys
        let safeAgentId = null;
        if (context.agentId) {
          try {
            const agent = await db.agents.getAgentById(context.agentId);
            if (agent) {
              safeAgentId = context.agentId;
            }
          } catch (err) {
            // Silently continue without the agent ID
          }
        }
        
        await db.llmLogs.createLog({
          id,
          operation,
          model,
          prompt: `${provider} ${model} request (too large for DB)`,
          response: null,
          tokensPrompt: tokenUsage.promptTokens,
          tokensCompletion: tokenUsage.completionTokens,
          costUsd,
          durationMs,
          status,
          errorMessage: `Original save failed: ${dbError.message}`,
          agentId: safeAgentId,
          planId: context.planId || null
        });
      } catch (retryError) {
        console.error('Failed to save even minimal LLM log:', retryError);
      }
    }
  } catch (error: any) {
    console.error('Error in LLM logging:', error);
  }
}