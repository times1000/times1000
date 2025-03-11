import * as openai from './openai';
// Temporarily removed Anthropic import until dependency is installed
// import * as anthropic from './anthropic';
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
  
  // Route to appropriate provider
  switch (provider) {
    case 'anthropic':
    case 'claude':
      // Temporarily only support OpenAI until Anthropic dependency is installed
      console.warn('Anthropic provider not currently available, using OpenAI instead');
      // Set default model
      config.model = 'gpt-4o';
      return openai.chatCompletion(messages, config, context);
      
    case 'openai':
    default:
      // Set default model if not specified
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
  
  // Currently, only OpenAI supports embeddings in our implementation
  if (provider !== 'openai') {
    console.warn(`Embedding provider "${provider}" not supported, using OpenAI`);
  }
  
  return openai.generateEmbedding(
    text, 
    config.model || 'text-embedding-3-small', 
    context
  );
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