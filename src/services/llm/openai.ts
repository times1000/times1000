import OpenAI from 'openai';
import type { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import { LLMMessage, LLMChatCompletionResponse, ModelConfig, LLMEmbeddingResponse, RequestContext } from './types';
import { logLLMRequest } from './logger';
import { calculateCost } from './pricing';

// Check for API key and log warning if missing
if (!process.env.OPENAI_API_KEY) {
  console.warn('WARNING: OPENAI_API_KEY environment variable is not set. OpenAI API calls will fail.');
}

// Initialize OpenAI client with the API key (no fallback)
const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

/**
 * Generate a chat completion using OpenAI
 */
export async function chatCompletion(
  messages: LLMMessage[],
  config: ModelConfig = { model: 'gpt-4o' },
  context: RequestContext = {}
): Promise<LLMChatCompletionResponse> {
  const startTime = Date.now();
  let status = 'completed';
  let errorMessage = null;
  
  try {
    // Extract configuration
    const model = config.model || 'gpt-4o';
    const temperature = config.temperature ?? 0.7;
    const maxTokens = config.maxTokens ?? 1000;
    
    // Rough estimate for logging if API fails
    const promptText = messages.map(m => m.content).join(' ');
    const tokensPrompt = Math.round(promptText.length / 4);
    
    // Format messages for OpenAI API - properly handle function role
    const openaiMessages: ChatCompletionMessageParam[] = [];
    
    // Process each message with proper typing
    for (const m of messages) {
      if (m.role === 'system') {
        openaiMessages.push({ role: 'system', content: m.content });
      } else if (m.role === 'user') {
        openaiMessages.push({ role: 'user', content: m.content });
      } else if (m.role === 'assistant') {
        openaiMessages.push({ role: 'assistant', content: m.content });
      } else if (m.role === 'function') {
        if (!m.name) {
          throw new Error('Function messages require a name property');
        }
        openaiMessages.push({ role: 'function', content: m.content, name: m.name });
      } else {
        // This should never happen due to TypeScript, but just in case
        throw new Error(`Unknown role type: ${m.role}`);
      }
    }
    
    // Call OpenAI API
    const response = await client.chat.completions.create({
      model,
      messages: openaiMessages,
      temperature,
      max_tokens: maxTokens,
    });
    
    // Calculate duration
    const durationMs = Date.now() - startTime;
    
    // Extract response content
    const content = response.choices[0].message.content || '';
    
    // Get token usage from response
    const tokensPromptActual = response.usage?.prompt_tokens || tokensPrompt;
    const tokensCompletion = response.usage?.completion_tokens || Math.round(content.length / 4);
    const tokenUsage = {
      promptTokens: tokensPromptActual,
      completionTokens: tokensCompletion,
      totalTokens: tokensPromptActual + tokensCompletion
    };
    
    // Calculate cost
    const costUsd = calculateCost('openai', model, tokensPromptActual, tokensCompletion);
    
    // Log request to database
    await logLLMRequest({
      provider: 'openai',
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
      finishReason: response.choices[0].finish_reason
    };
  } catch (error: any) {
    status = 'error';
    errorMessage = error.message;
    console.error('OpenAI chat completion error:', error);
    
    // Log failed request
    const durationMs = Date.now() - startTime;
    await logLLMRequest({
      provider: 'openai',
      model: config.model || 'gpt-4o',
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
    throw new Error(`OpenAI chat completion failed: ${error.message}`);
  }
}

/**
 * Generate embeddings using OpenAI
 */
export async function generateEmbedding(
  text: string,
  model: string = 'text-embedding-3-small',
  context: RequestContext = {}
): Promise<LLMEmbeddingResponse> {
  const startTime = Date.now();
  let status = 'completed';
  let errorMessage = null;
  
  try {
    // Estimate token count for logging
    const tokensPrompt = Math.round(text.length / 4);
    
    // Call OpenAI API
    const response = await client.embeddings.create({
      model,
      input: text,
    });
    
    // Calculate duration
    const durationMs = Date.now() - startTime;
    
    // Get token usage from response
    const tokensPromptActual = response.usage?.prompt_tokens || tokensPrompt;
    const tokenUsage = {
      promptTokens: tokensPromptActual,
      completionTokens: 0,
      totalTokens: tokensPromptActual
    };
    
    // Calculate cost
    const costUsd = calculateCost('openai', model, tokensPromptActual, 0);
    
    // Log request to database
    await logLLMRequest({
      provider: 'openai',
      model,
      operation: context.operation || 'embedding',
      prompt: text,
      tokenUsage,
      costUsd,
      durationMs,
      context
    });
    
    // Return standardized response
    return {
      embedding: response.data[0].embedding,
      tokenUsage,
      model
    };
  } catch (error: any) {
    status = 'error';
    errorMessage = error.message;
    console.error('OpenAI embedding error:', error);
    
    // Log failed request
    const durationMs = Date.now() - startTime;
    await logLLMRequest({
      provider: 'openai',
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
    
    // Re-throw with more context
    throw new Error(`OpenAI embedding failed: ${error.message}`);
  }
}