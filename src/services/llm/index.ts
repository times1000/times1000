import * as openai from './openai';
import * as anthropic from './anthropic';
import { LLMMessage, LLMChatCompletionResponse, ModelConfig, LLMEmbeddingResponse, RequestContext } from './types';
import { logLLMRequest } from './logger';
import { calculateCost } from './pricing';

// Determine default providers
const defaultChatProvider = process.env.DEFAULT_LLM_PROVIDER?.toLowerCase() || 'openai';
const defaultEmbeddingProvider = process.env.DEFAULT_EMBEDDING_PROVIDER?.toLowerCase() || 'openai';

/**
 * Generate a chat completion using the configured provider
 */
export async function chatCompletion(
  messages: LLMMessage[],
  config: ModelConfig & { provider?: string } = { model: 'gpt-4o' },
  context: RequestContext = {}
): Promise<LLMChatCompletionResponse> {
  // Determine which provider to use
  const provider = config.provider?.toLowerCase() || defaultChatProvider;
  
  // Check if environment variables are properly set
  if (provider === 'openai' && !process.env.OPENAI_API_KEY) {
    throw new Error('OPENAI_API_KEY environment variable is not set. Please configure the API key in environment variables.');
  }
  
  if ((provider === 'anthropic' || provider === 'claude') && !process.env.ANTHROPIC_API_KEY) {
    throw new Error('ANTHROPIC_API_KEY environment variable is not set. Please configure the API key in environment variables.');
  }
  
  // Route to appropriate provider
  switch (provider) {
    case 'anthropic':
    case 'claude':
      // Set default model if not appropriate for Anthropic
      if (!config.model || !config.model.startsWith('claude-')) {
        config.model = 'claude-3-sonnet';
      }
      return anthropic.chatCompletion(messages, config, context);
      
    case 'openai':
    default:
      // Set default model if not appropriate for OpenAI
      if (!config.model || config.model.startsWith('claude-')) {
        config.model = 'gpt-4o';
      }
      return openai.chatCompletion(messages, config, context);
  }
}

/**
 * Generate text embeddings using the configured provider
 */
export async function generateEmbedding(
  text: string,
  config: { model?: string; provider?: string } = {},
  context: RequestContext = {}
): Promise<LLMEmbeddingResponse> {
  // Determine which provider to use
  const provider = config.provider?.toLowerCase() || defaultEmbeddingProvider;
  
  // Check if environment variables are properly set
  if (provider === 'openai' && !process.env.OPENAI_API_KEY) {
    throw new Error('OPENAI_API_KEY environment variable is not set. Please configure the API key in environment variables.');
  }
  
  if ((provider === 'anthropic' || provider === 'claude') && !process.env.ANTHROPIC_API_KEY) {
    throw new Error('ANTHROPIC_API_KEY environment variable is not set. Please configure the API key in environment variables.');
  }
  
  // Route to appropriate provider
  switch (provider) {
    case 'anthropic':
    case 'claude':
      // Anthropic doesn't support embeddings yet, but we'll try to call it
      // (it will throw an appropriate error with proper logging)
      return anthropic.generateEmbedding(text, config.model, context);
      
    case 'openai':
    default:
      return openai.generateEmbedding(
        text, 
        config.model || 'text-embedding-3-small', 
        context
      );
  }
}

/**
 * Extract structured information from text
 */
export async function extractInfo<T = any>(
  text: string,
  instructions: string,
  config: ModelConfig & { provider?: string } = { model: 'gpt-4o' },
  context: RequestContext = {}
): Promise<T> {
  // Create messages for the extraction
  const messages: LLMMessage[] = [
    {
      role: 'system',
      content: `You are an AI assistant that extracts structured information from text. ${instructions} Respond only with a JSON object containing the extracted information.`
    },
    { 
      role: 'user', 
      content: text 
    }
  ];
  
  // Add operation context
  const contextWithOperation = {
    ...context,
    operation: context.operation || 'extract_info'
  };
  
  // Use chat completion to get structured data
  const response = await chatCompletion(messages, config, contextWithOperation);
  
  // Parse and return the result
  try {
    return JSON.parse(response.content) as T;
  } catch (error) {
    console.error('Failed to parse extracted info as JSON:', error);
    throw new Error('Failed to parse extracted information as JSON');
  }
}

// Re-export helper functions so they can be used directly
export { logLLMRequest, calculateCost };

// Export types for consumers
export type { LLMMessage, LLMChatCompletionResponse, ModelConfig, LLMEmbeddingResponse, RequestContext };