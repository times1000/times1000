/**
 * Common types for LLM services
 */

// Base message type used across all providers
export interface LLMMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

// Common token usage interface
export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
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
}

// Chat completion response
export interface LLMChatCompletionResponse {
  content: string;
  tokenUsage: TokenUsage;
  model: string;
  finishReason?: string;
}

// Embedding response
export interface LLMEmbeddingResponse {
  embedding: number[];
  tokenUsage: TokenUsage;
  model: string;
}