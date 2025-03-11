import * as openai from './openai';
import * as anthropic from './anthropic';
import { 
  LLMMessage, 
  LLMChatCompletionResponse, 
  ModelConfig, 
  LLMEmbeddingResponse, 
  RequestContext,
  ExecutionOptions,
  ExecutionStrategy,
  ToolFunction
} from './types';
import { logLLMRequest } from './logger';
import { calculateCost } from './pricing';
import { 
  generateAndExecuteCode, 
  isClaudeCodeAvailable,
  getCodeExecutionPath,
  getAvailableMcpServices
} from './claude-code-execution';

// Export all centralized modules
export * from './prompts';
export * from './config';
export * from './tools';
export * from './logging-format';

// Import central configuration
import { 
  DEFAULT_MODELS, 
  PROVIDER_CONFIG, 
  TEMPERATURE_SETTINGS,
  TOKEN_LIMITS,
  CODE_EXECUTION_CONFIG,
  OPERATION_NAMES
} from './config';

// Use centralized configuration instead of directly accessing environment variables
const defaultChatProvider = PROVIDER_CONFIG.DEFAULT_PROVIDER;
const defaultEmbeddingProvider = PROVIDER_CONFIG.DEFAULT_EMBEDDING_PROVIDER;
const enableCodeExecution = CODE_EXECUTION_CONFIG.ENABLED;

// Check Claude Code availability during startup
let claudeCodeAvailable = false;
if (enableCodeExecution) {
  claudeCodeAvailable = isClaudeCodeAvailable();
  console.log(`Claude Code execution ${claudeCodeAvailable ? 'is' : 'is not'} available`);
  
  if (claudeCodeAvailable) {
    console.log(`Code execution path: ${getCodeExecutionPath()}`);
    console.log(`Available MCP services: ${getAvailableMcpServices().join(', ')}`);
  }
}

/**
 * Generate a chat completion using the configured provider
 * Now supports tool execution via Claude Code
 */
export async function chatCompletion(
  messages: LLMMessage[],
  config: ExecutionOptions = { model: 'gpt-4o' },
  context: RequestContext = {}
): Promise<LLMChatCompletionResponse> {
  // Determine execution strategy and provider
  const executionStrategy = shouldUseToolExecution(config) ? 'tools' : 'standard';
  const provider = config.provider?.toLowerCase() || defaultChatProvider;
  
  // Check if environment variables are properly set
  if (provider === 'openai' && !process.env.OPENAI_API_KEY) {
    throw new Error('OPENAI_API_KEY environment variable is not set. Please configure the API key in environment variables.');
  }
  
  if ((provider === 'anthropic' || provider === 'claude') && !process.env.ANTHROPIC_API_KEY) {
    throw new Error('ANTHROPIC_API_KEY environment variable is not set. Please configure the API key in environment variables.');
  }
  
  // If using code execution and it's enabled and available
  if (executionStrategy === 'tools' && enableCodeExecution && claudeCodeAvailable) {
    console.log('Using Claude Code CLI for code execution');
    
    try {
      // Generate and execute code with Claude Code CLI
      const { result, toolUsage } = await generateAndExecuteCode(
        messages,
        {
          ...context,
          executionStrategy: 'code_execution'
        }
      );
      
      // Log the code execution
      await logLLMRequest({
        provider: 'claude-code',
        model: 'claude-3-opus', // Assuming Claude Code uses opus
        operation: context.operation || 'code_execution',
        prompt: JSON.stringify(messages),
        response: result,
        tokenUsage: {
          promptTokens: 0, // These are not available from Claude Code CLI
          completionTokens: 0,
          totalTokens: 0
        },
        costUsd: 0, // Would need a different pricing model
        durationMs: 0, // Not tracked by CLI
        context: {
          ...context,
          executionMode: 'code_execution'
        },
        toolUsage
      });
      
      // Return the response in our standard format
      return {
        content: result,
        model: 'claude-3-opus',
        tokenUsage: {
          promptTokens: 0,
          completionTokens: 0,
          totalTokens: 0
        },
        finishReason: 'stop',
        toolUsage
      };
    } catch (error) {
      console.error('Claude Code execution failed, falling back to standard LLM:', error);
      // Will fall through to standard execution
    }
  }
  
  // Standard execution path
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
 * Determine if we should use tool execution based on config and environment
 */
function shouldUseToolExecution(config: ExecutionOptions): boolean {
  // If explicitly specified in config, use that
  if (config.executionStrategy === 'tools') {
    return true;
  }
  
  // If tools are provided, use tool execution
  if (config.tools && config.tools.length > 0) {
    return true;
  }
  
  // Default to environment setting
  return enableCodeExecution && claudeCodeAvailable;
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
  config: ModelConfig & { provider?: string } = { model: DEFAULT_MODELS.EXTRACTION },
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
    operation: context.operation || OPERATION_NAMES.EXTRACT_INFO
  };
  
  // Set appropriate temperature for extraction (lower is better for factual extraction)
  const extractionConfig = {
    ...config,
    temperature: config.temperature ?? TEMPERATURE_SETTINGS.EXTRACTION
  };
  
  // Use chat completion to get structured data
  const response = await chatCompletion(messages, extractionConfig, contextWithOperation);
  
  // Parse and return the result
  try {
    return JSON.parse(response.content) as T;
  } catch (error) {
    console.error('Failed to parse extracted info as JSON:', error);
    throw new Error('Failed to parse extracted information as JSON');
  }
}

/**
 * Execute code generation and execution with Claude Code CLI
 */
export async function executeCodeWithClaudeCode(
  messages: LLMMessage[],
  context: RequestContext = {}
): Promise<string> {
  if (!enableCodeExecution || !claudeCodeAvailable) {
    throw new Error('Code execution is disabled or Claude Code is not available');
  }
  
  try {
    // Execute the code generation and execution
    const { result } = await generateAndExecuteCode(messages, context);
    return result;
  } catch (error) {
    console.error('Error executing code with Claude Code:', error);
    throw new Error(`Code execution failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Check if Claude Code is available for code execution
 */
export function isCodeExecutionAvailable(): boolean {
  return enableCodeExecution && claudeCodeAvailable;
}

/**
 * Get available MCP services for code execution
 */
export function getAvailableMcpServicesForCode(): string[] {
  if (!enableCodeExecution || !claudeCodeAvailable) {
    return [];
  }
  
  return getAvailableMcpServices();
}

// Re-export helper functions so they can be used directly
export { logLLMRequest, calculateCost };

// Export types for consumers
export type { 
  LLMMessage, 
  LLMChatCompletionResponse, 
  ModelConfig, 
  LLMEmbeddingResponse, 
  RequestContext,
  ExecutionOptions,
  ExecutionStrategy,
  ToolFunction,
  ToolCallResult 
} from './types';