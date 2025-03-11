import Anthropic from '@anthropic-ai/sdk';
import { LLMMessage, LLMChatCompletionResponse, ModelConfig, LLMEmbeddingResponse, RequestContext } from './types';
import { logLLMRequest } from './logger';
import { calculateCost } from './pricing';

// Initialize Anthropic client with fallback to dummy key for development
const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || 'sk-dummy-key-for-development',
});

/**
 * Generate a chat completion using Anthropic Claude
 */
export async function chatCompletion(
  messages: LLMMessage[],
  config: ModelConfig = { model: 'claude-3-sonnet' },
  context: RequestContext = {}
): Promise<LLMChatCompletionResponse> {
  const startTime = Date.now();
  let status = 'completed';
  let errorMessage = null;
  
  try {
    // Extract configuration
    const model = config.model || 'claude-3-sonnet';
    const temperature = config.temperature ?? 0.7;
    const maxTokens = config.maxTokens ?? 1000;
    
    // Rough estimate for logging if API fails
    const promptText = messages.map(m => m.content).join(' ');
    const tokensPrompt = Math.round(promptText.length / 4);
    
    // Format messages for Anthropic API
    const systemMessage = messages.find(m => m.role === 'system')?.content || '';
    
    // Remove system messages from the regular messages array
    // Anthropic only accepts 'user' and 'assistant' roles
    const userAssistantMessages = messages
      .filter(m => m.role !== 'system')
      .map(m => ({
        role: m.role as 'user' | 'assistant', // Type assertion for Anthropic's API
        content: m.content
      }));
    
    // Call Anthropic API
    const response = await client.messages.create({
      model,
      messages: userAssistantMessages,
      system: systemMessage,
      temperature,
      max_tokens: maxTokens,
    });
    
    // Calculate duration
    const durationMs = Date.now() - startTime;
    
    // Extract response content
    const content = response.content[0].text;
    
    // Get token usage from response
    const tokensPromptActual = response.usage?.input_tokens || tokensPrompt;
    const tokensCompletion = response.usage?.output_tokens || Math.round(content.length / 4);
    const tokenUsage = {
      promptTokens: tokensPromptActual,
      completionTokens: tokensCompletion,
      totalTokens: tokensPromptActual + tokensCompletion
    };
    
    // Calculate cost
    const costUsd = calculateCost('anthropic', model, tokensPromptActual, tokensCompletion);
    
    // Log request to database
    await logLLMRequest({
      provider: 'anthropic',
      model,
      operation: context.operation || 'chat',
      prompt: messages,
      response: content,
      tokenUsage,
      costUsd,
      durationMs,
      context
    });
    
    // Return standardized response
    return {
      content,
      tokenUsage,
      model,
      finishReason: response.stop_reason
    };
  } catch (error: any) {
    status = 'error';
    errorMessage = error.message;
    console.error('Anthropic chat completion error:', error);
    
    // Log failed request
    const durationMs = Date.now() - startTime;
    await logLLMRequest({
      provider: 'anthropic',
      model: config.model || 'claude-3-sonnet',
      operation: context.operation || 'chat',
      prompt: messages,
      tokenUsage: {
        promptTokens: 0,
        completionTokens: 0,
        totalTokens: 0
      },
      costUsd: 0,
      durationMs,
      status,
      error: errorMessage,
      context
    });
    
    // Re-throw with more context
    throw new Error(`Anthropic chat completion failed: ${error.message}`);
  }
}

/**
 * Generate embeddings using Anthropic
 * Note: As of this implementation, Anthropic doesn't provide a public embeddings API
 * This is a placeholder that will throw an appropriate error
 */
export async function generateEmbedding(
  text: string,
  model: string = 'claude-3-sonnet',
  context: RequestContext = {}
): Promise<LLMEmbeddingResponse> {
  const startTime = Date.now();
  const status = 'error';
  const errorMessage = 'Anthropic does not currently provide a public embeddings API';
  
  try {
    console.error(errorMessage);
    
    // Log failed request
    const durationMs = Date.now() - startTime;
    await logLLMRequest({
      provider: 'anthropic',
      model,
      operation: context.operation || 'embedding',
      prompt: text,
      tokenUsage: {
        promptTokens: 0,
        completionTokens: 0,
        totalTokens: 0
      },
      costUsd: 0,
      durationMs,
      status,
      error: errorMessage,
      context
    });
    
    // Throw appropriate error
    throw new Error(errorMessage);
  } catch (error: any) {
    // Re-throw with more context if it's not our original error
    if (error.message !== errorMessage) {
      console.error('Anthropic embedding error:', error);
      throw new Error(`Anthropic embedding failed: ${error.message}`);
    }
    throw error;
  }
}