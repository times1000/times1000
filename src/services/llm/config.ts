/**
 * Centralized LLM configuration settings and defaults
 * This file contains all configuration constants used by the LLM services
 */

// Default models by task
export const DEFAULT_MODELS = {
  // Plan generation and agent creation
  PLAN_GENERATION: process.env.DEFAULT_PLAN_MODEL || 'gpt-4o',
  AGENT_METADATA: process.env.DEFAULT_METADATA_MODEL || 'gpt-4o',
  
  // Plan execution
  PLAN_EXECUTION: process.env.DEFAULT_PLAN_EXECUTION_MODEL || 'gpt-4o',
  
  // Step execution
  STEP_EXECUTION: process.env.DEFAULT_STEP_MODEL || 'gpt-4o-mini',
  
  // Follow-up suggestions
  FOLLOWUP_GENERATION: process.env.DEFAULT_FOLLOWUP_MODEL || 'gpt-4o',
  
  // Content extraction and embedding
  EMBEDDING: process.env.DEFAULT_EMBEDDING_MODEL || 'text-embedding-3-small',
  EXTRACTION: process.env.DEFAULT_EXTRACTION_MODEL || 'gpt-4o-mini',
  
  // Default models by provider
  OPENAI_DEFAULT: 'gpt-4o',
  ANTHROPIC_DEFAULT: 'claude-3-sonnet'
};

// Provider defaults and settings
export const PROVIDER_CONFIG = {
  // Default provider for different operations
  DEFAULT_PROVIDER: process.env.DEFAULT_LLM_PROVIDER?.toLowerCase() || 'openai',
  DEFAULT_EMBEDDING_PROVIDER: process.env.DEFAULT_EMBEDDING_PROVIDER?.toLowerCase() || 'openai',
  
  // Provider-specific settings
  OPENAI: {
    API_BASE_URL: process.env.OPENAI_API_BASE || 'https://api.openai.com/v1',
    ORGANIZATION_ID: process.env.OPENAI_ORGANIZATION_ID
  },
  ANTHROPIC: {
    API_BASE_URL: process.env.ANTHROPIC_API_BASE || 'https://api.anthropic.com'
  }
};

// Temperature settings for different tasks
export const TEMPERATURE_SETTINGS = {
  PLAN_GENERATION: parseFloat(process.env.PLAN_TEMPERATURE || '0.7'),
  STEP_EXECUTION: parseFloat(process.env.STEP_TEMPERATURE || '0.7'),
  FOLLOWUP_GENERATION: parseFloat(process.env.FOLLOWUP_TEMPERATURE || '0.7'),
  EXTRACTION: parseFloat(process.env.EXTRACTION_TEMPERATURE || '0.2')
};

// Token limits for different models and tasks
export const TOKEN_LIMITS = {
  PLAN_GENERATION: parseInt(process.env.PLAN_MAX_TOKENS || '2000'),
  STEP_EXECUTION: parseInt(process.env.STEP_MAX_TOKENS || '1500'),
  FOLLOWUP_GENERATION: parseInt(process.env.FOLLOWUP_MAX_TOKENS || '1000'),
  AGENT_METADATA: parseInt(process.env.METADATA_MAX_TOKENS || '300')
};

// Code execution configuration
export const CODE_EXECUTION_CONFIG = {
  ENABLED: process.env.ENABLE_CODE_EXECUTION === 'true',
  TIMEOUT_MS: parseInt(process.env.CODE_EXECUTION_TIMEOUT || '60000'),
  MAX_OUTPUT_SIZE: parseInt(process.env.CODE_EXECUTION_MAX_OUTPUT || '10000')
};

// Operation names for tracking and logging
export const OPERATION_NAMES = {
  PLAN_GENERATION: 'generate_plan',
  STEP_EXECUTION: 'execute_step',
  FOLLOWUP_GENERATION: 'generate_followups',
  AGENT_METADATA: 'generate_agent_metadata',
  EXTRACT_INFO: 'extract_info',
  CODE_EXECUTION: 'code_execution',
  EMBEDDING: 'generate_embedding'
};