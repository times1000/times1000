/**
 * Standardized logging formats for LLM requests and responses
 * This provides consistent structure for logging across the application
 */
import { LLMMessage, TokenUsage, ToolUsage } from './types';

/**
 * Standard request log format
 */
export interface LLMRequestLog {
  // Unique identifier for the request
  requestId: string;
  
  // Basic request information
  timestamp: string;
  provider: string;
  model: string;
  operation: string;
  
  // Request details
  prompt: string | LLMMessage[];
  temperature?: number;
  maxTokens?: number;
  
  // Contextual information
  agentId?: string;
  planId?: string;
  stepId?: string;
  
  // Custom metadata
  metadata?: Record<string, any>;
}

/**
 * Standard response log format
 */
export interface LLMResponseLog {
  // Reference to the request
  requestId: string;
  
  // Basic response information
  timestamp: string;
  status: 'completed' | 'failed' | 'partial';
  durationMs: number;
  
  // Response content
  response?: string;
  error?: string;
  
  // Usage metrics
  tokenUsage: TokenUsage;
  costUsd: number;
  toolUsage?: ToolUsage;
  
  // Response metadata
  finishReason?: string;
  metadata?: Record<string, any>;
}

/**
 * Formats a request for logging
 */
export function formatRequestForLogging(
  provider: string,
  model: string,
  operation: string,
  prompt: LLMMessage[] | string,
  options: {
    temperature?: number;
    maxTokens?: number;
    agentId?: string;
    planId?: string;
    stepId?: string;
    requestId?: string;
    metadata?: Record<string, any>;
  } = {}
): LLMRequestLog {
  return {
    requestId: options.requestId || generateRequestId(),
    timestamp: new Date().toISOString(),
    provider,
    model,
    operation,
    prompt: typeof prompt === 'string' ? prompt : JSON.stringify(prompt),
    temperature: options.temperature,
    maxTokens: options.maxTokens,
    agentId: options.agentId,
    planId: options.planId,
    stepId: options.stepId,
    metadata: options.metadata
  };
}

/**
 * Formats a response for logging
 */
export function formatResponseForLogging(
  requestId: string,
  status: 'completed' | 'failed' | 'partial',
  tokenUsage: TokenUsage,
  costUsd: number,
  options: {
    response?: string;
    error?: string;
    durationMs?: number;
    toolUsage?: ToolUsage;
    finishReason?: string;
    metadata?: Record<string, any>;
  } = {}
): LLMResponseLog {
  return {
    requestId,
    timestamp: new Date().toISOString(),
    status,
    durationMs: options.durationMs || 0,
    response: options.response,
    error: options.error,
    tokenUsage,
    costUsd,
    toolUsage: options.toolUsage,
    finishReason: options.finishReason,
    metadata: options.metadata
  };
}

/**
 * Generates a unique request ID
 */
function generateRequestId(): string {
  return `llm_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
}

/**
 * Creates a summary of the request and response for quick viewing
 */
export function createRequestSummary(request: LLMRequestLog, response?: LLMResponseLog): string {
  const summary = [
    `[${request.timestamp}] ${request.provider.toUpperCase()} ${request.model} - ${request.operation}`,
    `Agent: ${request.agentId || 'None'} | Plan: ${request.planId || 'None'}`
  ];
  
  if (response) {
    summary.push(
      `Status: ${response.status} | Duration: ${response.durationMs}ms`,
      `Tokens: ${response.tokenUsage.totalTokens} | Cost: $${response.costUsd.toFixed(6)}`
    );
    
    if (response.toolUsage && response.toolUsage.toolCalls > 0) {
      summary.push(`Tool calls: ${response.toolUsage.toolCalls}`);
    }
    
    if (response.error) {
      summary.push(`Error: ${response.error}`);
    }
  }
  
  return summary.join('\n');
}