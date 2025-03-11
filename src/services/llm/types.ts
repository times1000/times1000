/**
 * Common types for LLM services
 */

// Base message type used across all providers
export interface LLMMessage {
  role: 'system' | 'user' | 'assistant' | 'function';
  content: string;
  name?: string;
}

// Common token usage interface
export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

// Tool usage tracking interface
export interface ToolUsage {
  toolCalls: number;
  toolRevenue?: number;
}

// Common pricing interface
export interface ModelPricing {
  input: number;  // Cost per 1K tokens for input
  output: number; // Cost per 1K tokens for output
}

// Model configuration interface
export interface ModelConfig {
  model: string;
  temperature?: number;
  maxTokens?: number;
}

// Request context for logging
export interface RequestContext {
  agentId?: string;
  planId?: string;
  operation?: string;
  [key: string]: string | undefined;
}

// Chat completion response
export interface LLMChatCompletionResponse {
  content: string;
  tokenUsage: TokenUsage;
  model: string;
  finishReason?: string;
  toolUsage?: ToolUsage;
}

// Embedding response
export interface LLMEmbeddingResponse {
  embedding: number[];
  tokenUsage: TokenUsage;
  model: string;
}

// Tool function interface
export interface ToolFunction {
  name: string;
  description: string;
  parameters: Record<string, any>;
}

// Tool call result interface
export interface ToolCallResult {
  functionName: string;
  arguments: Record<string, any>;
  result: any;
}

// Execution strategy type
export type ExecutionStrategy = 'standard' | 'tools';

// Tool configuration interface
export interface ToolConfig {
  enabled: boolean;
  provider: 'openai' | 'anthropic' | 'claude-code';
}

// Execution options extending model config
export interface ExecutionOptions extends ModelConfig {
  executionStrategy?: ExecutionStrategy;
  tools?: ToolFunction[];
  provider?: string;
}