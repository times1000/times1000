import { LLMMessage, LLMChatCompletionResponse, ModelConfig, RequestContext } from './types';

/**
 * STUB: This is a placeholder for the Anthropic Claude API client
 * The actual implementation will be added once the dependency is installed
 * 
 * For now, we're directing all requests to OpenAI in the index.ts file.
 */
export async function chatCompletion(
  messages: LLMMessage[],
  _config: ModelConfig = { model: 'claude-3-sonnet' },
  _context: RequestContext = {}
): Promise<LLMChatCompletionResponse> {
  throw new Error('Anthropic implementation not available');
}