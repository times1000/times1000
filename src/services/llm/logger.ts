import db from '../../db';
// Force reload db to ensure fresh connection
db.testConnection();
import { v4 as uuidv4 } from 'uuid';
import { LLMMessage, TokenUsage, RequestContext, ToolUsage } from './types';
import { logLLMOperation, logSystemOperation } from '../../api/services/logging-service';

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
  context = {},
  toolUsage
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
  toolUsage?: ToolUsage;
}): Promise<void> {
  try {
    // Prepare prompt for storage
    const promptString = typeof prompt === 'string' 
      ? prompt 
      : JSON.stringify(prompt);
    
    // Log to console for debugging (minimal details)
    const logData = {
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
      planId: context.planId,
      ...(toolUsage ? {
        toolCalls: toolUsage.toolCalls,
        toolRevenue: toolUsage.toolRevenue
      } : {})
    };
    
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
    
    // Log LLM operation
    await logLLMOperation(operation, {
      model,
      provider,
      prompt: promptString,
      response,
      tokensPrompt: tokenUsage.promptTokens,
      tokensCompletion: tokenUsage.completionTokens,
      costUsd,
      durationMs,
      status,
      error,
      agentId: safeAgentId,
      planId: context.planId || null
    });
    
    // Also log a system entry for the operation
    await logSystemOperation('llm_request', {
      source: 'llm_service',
      message: `${provider} ${model} ${operation}`,
      details: JSON.stringify({
        model,
        provider,
        operation,
        tokenUsage,
        costUsd,
        status,
        ...(toolUsage ? { toolUsage } : {})
      }),
      level: error ? 'error' : 'info',
      durationMs,
      agentId: safeAgentId,
      planId: context.planId || null
    });
  } catch (error: any) {
    console.error('Error in LLM logging:', error);
    
    // Try to log the error as a system log
    try {
      await logSystemOperation('llm_log_error', {
        source: 'llm_service',
        message: `Error logging LLM ${provider} ${model} operation: ${error.message}`,
        level: 'error',
        agentId: context.agentId || null,
        planId: context.planId || null
      });
    } catch (secondaryError) {
      console.error('Failed to log LLM logging error:', secondaryError);
    }
  }
}