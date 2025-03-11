import { LLMMessage, LLMChatCompletionResponse, ModelConfig, RequestContext } from './types';

/**
 * Placeholder implementation for the Anthropic Claude API client
 * This returns a dummy response instead of throwing an error
 */
export async function chatCompletion(
  messages: LLMMessage[],
  config: ModelConfig = { model: 'claude-3-sonnet' },
  _context: RequestContext = {}
): Promise<LLMChatCompletionResponse> {
  console.warn('Using placeholder Anthropic implementation');
  
  // Return a dummy/fallback response in LLMChatCompletionResponse format
  return {
    content: 'This is a placeholder response. The Anthropic API integration is not fully implemented.',
    tokenUsage: {
      promptTokens: 0,
      completionTokens: 0,
      totalTokens: 0
    },
    model: config.model || 'claude-3-sonnet',
    finishReason: 'stop'
  };
}