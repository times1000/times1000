import { ModelPricing } from './types';

// OpenAI model pricing
// Prices are per 1K tokens, in USD
// Source: https://platform.openai.com/docs/pricing
const openAIPricing: Record<string, ModelPricing> = {
  // GPT-4.5 Preview models
  'gpt-4.5-preview': { input: 0.075, output: 0.15 },
  'gpt-4.5-preview-2025-02-27': { input: 0.075, output: 0.15 },
  
  // GPT-4o models
  'gpt-4o': { input: 0.0025, output: 0.01 },
  'gpt-4o-2024-11-20': { input: 0.0025, output: 0.01 },
  'gpt-4o-2024-08-06': { input: 0.0025, output: 0.01 },
  'gpt-4o-2024-05-13': { input: 0.005, output: 0.015 },
  
  // GPT-4o Audio Preview models
  'gpt-4o-audio-preview': { input: 0.0025, output: 0.01 },
  'gpt-4o-audio-preview-2024-12-17': { input: 0.0025, output: 0.01 },
  'gpt-4o-audio-preview-2024-10-01': { input: 0.0025, output: 0.01 },
  
  // GPT-4o Realtime Preview models
  'gpt-4o-realtime-preview': { input: 0.005, output: 0.02 },
  'gpt-4o-realtime-preview-2024-12-17': { input: 0.005, output: 0.02 },
  'gpt-4o-realtime-preview-2024-10-01': { input: 0.005, output: 0.02 },
  
  // GPT-4o Mini models
  'gpt-4o-mini': { input: 0.00015, output: 0.0006 },
  'gpt-4o-mini-2024-07-18': { input: 0.00015, output: 0.0006 },
  
  // GPT-4o Mini Audio Preview models
  'gpt-4o-mini-audio-preview': { input: 0.00015, output: 0.0006 },
  'gpt-4o-mini-audio-preview-2024-12-17': { input: 0.00015, output: 0.0006 },
  
  // GPT-4o Mini Realtime Preview models
  'gpt-4o-mini-realtime-preview': { input: 0.0006, output: 0.0024 },
  'gpt-4o-mini-realtime-preview-2024-12-17': { input: 0.0006, output: 0.0024 },
  
  // O1 models
  'o1': { input: 0.015, output: 0.06 },
  'o1-2024-12-17': { input: 0.015, output: 0.06 },
  'o1-preview-2024-09-12': { input: 0.015, output: 0.06 },
  
  // O3 Mini models
  'o3-mini': { input: 0.0011, output: 0.0044 },
  'o3-mini-2025-01-31': { input: 0.0011, output: 0.0044 },
  
  // O1 Mini models
  'o1-mini': { input: 0.0011, output: 0.0044 },
  'o1-mini-2024-09-12': { input: 0.0011, output: 0.0044 },
  
  // Legacy models (kept for backward compatibility)
  'gpt-4': { input: 0.03, output: 0.06 },
  'gpt-4-32k': { input: 0.06, output: 0.12 },
  'gpt-4-turbo': { input: 0.01, output: 0.03 },
  'gpt-4-vision-preview': { input: 0.01, output: 0.03 },
  'gpt-3.5-turbo': { input: 0.0005, output: 0.0015 },
  'gpt-3.5-turbo-instruct': { input: 0.0015, output: 0.0020 },
  'gpt-3.5-turbo-16k': { input: 0.003, output: 0.004 },
  
  // Text embedding models
  'text-embedding-3-small': { input: 0.00002, output: 0 },
  'text-embedding-3-large': { input: 0.00013, output: 0 },
  'text-embedding-ada-002': { input: 0.0001, output: 0 }
};

// Anthropic Claude pricing
// Prices are per 1K tokens, in USD
// Source: https://anthropic.com/pricing
const claudePricing: Record<string, ModelPricing> = {
  // Claude 3 Opus
  'claude-3-opus-20240229': { input: 0.015, output: 0.075 },
  'claude-3-opus': { input: 0.015, output: 0.075 },
  
  // Claude 3 Sonnet
  'claude-3-sonnet-20240229': { input: 0.003, output: 0.015 },
  'claude-3-sonnet': { input: 0.003, output: 0.015 },
  
  // Claude 3 Haiku
  'claude-3-haiku-20240307': { input: 0.00025, output: 0.00125 },
  'claude-3-haiku': { input: 0.00025, output: 0.00125 },
  
  // Claude 3.5 Sonnet
  'claude-3-5-sonnet-20240620': { input: 0.003, output: 0.015 },
  'claude-3-5-sonnet': { input: 0.003, output: 0.015 },
};

/**
 * Calculate cost for an LLM API call based on token usage
 * 
 * @param provider The LLM provider (e.g., 'openai', 'anthropic')
 * @param model The specific model used
 * @param inputTokens Number of prompt tokens
 * @param outputTokens Number of completion tokens
 * @returns Cost in USD
 */
export function calculateCost(
  provider: string, 
  model: string, 
  inputTokens: number, 
  outputTokens: number
): number {
  let pricing: ModelPricing;
  
  // Select pricing based on provider
  switch (provider.toLowerCase()) {
    case 'openai':
      pricing = openAIPricing[model] || openAIPricing['gpt-4o'];
      break;
    case 'anthropic':
      pricing = claudePricing[model] || claudePricing['claude-3-sonnet'];
      break;
    default:
      // Unknown provider, use GPT-4o pricing as default
      console.warn(`Unknown provider "${provider}", using default pricing`);
      pricing = openAIPricing['gpt-4o'];
  }
  
  // Calculate and return cost (per 1K tokens)
  return (inputTokens / 1000 * pricing.input) + (outputTokens / 1000 * pricing.output);
}