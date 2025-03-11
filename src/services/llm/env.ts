/**
 * Centralized access to environment variables and validation
 * This provides a single source of truth for environment configurations
 */

// API Keys and Authentication
export const API_KEYS = {
  OPENAI: process.env.OPENAI_API_KEY,
  ANTHROPIC: process.env.ANTHROPIC_API_KEY,
  // Add others as needed
};

// Service configuration
export const SERVICE_CONFIG = {
  // Base service configuration
  PORT: parseInt(process.env.PORT || '3000'),
  HOST: process.env.HOST || 'localhost',
  NODE_ENV: process.env.NODE_ENV || 'development',
  
  // Database configuration
  DB_HOST: process.env.DB_HOST || 'localhost',
  DB_PORT: parseInt(process.env.DB_PORT || '3306'),
  DB_USER: process.env.DB_USER || 'root',
  DB_PASSWORD: process.env.DB_PASSWORD || '',
  DB_NAME: process.env.DB_NAME || 'times1000',
  
  // API configuration
  API_PREFIX: process.env.API_PREFIX || '/api',
  API_VERSION: process.env.API_VERSION || 'v1',
  
  // CORS configuration
  CORS_ORIGIN: process.env.CORS_ORIGIN || '*'
};

// Feature flags and toggles
export const FEATURE_FLAGS = {
  ENABLE_CODE_EXECUTION: process.env.ENABLE_CODE_EXECUTION === 'true',
  ENABLE_DEBUG_LOGGING: process.env.ENABLE_DEBUG_LOGGING === 'true',
  ENABLE_METRICS: process.env.ENABLE_METRICS === 'true',
  ENABLE_RATE_LIMITING: process.env.ENABLE_RATE_LIMITING === 'true',
  
  // Agent execution features
  AUTO_APPROVE_PLANS: process.env.AUTO_APPROVE_PLANS === 'true',
  ALLOW_CONCURRENT_EXECUTION: process.env.ALLOW_CONCURRENT_EXECUTION === 'true'
};

// Limits and thresholds
export const LIMITS = {
  MAX_AGENTS: parseInt(process.env.MAX_AGENTS || '50'),
  MAX_PLANS_PER_AGENT: parseInt(process.env.MAX_PLANS_PER_AGENT || '100'),
  MAX_STEPS_PER_PLAN: parseInt(process.env.MAX_STEPS_PER_PLAN || '20'),
  
  // Rate limiting
  RATE_LIMIT_WINDOW_MS: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '60000'),
  RATE_LIMIT_MAX_REQUESTS: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || '100'),
  
  // Cost management
  DAILY_COST_LIMIT_USD: parseFloat(process.env.DAILY_COST_LIMIT_USD || '10.0')
};

/**
 * Validates critical environment variables and returns any missing/invalid values
 */
export function validateEnvironment(): { valid: boolean; missing: string[]; invalid: string[] } {
  const missing: string[] = [];
  const invalid: string[] = [];
  
  // Check for required API keys
  if (!API_KEYS.OPENAI && !API_KEYS.ANTHROPIC) {
    missing.push('Either OPENAI_API_KEY or ANTHROPIC_API_KEY must be provided');
  }
  
  // Check database connection info
  if (!SERVICE_CONFIG.DB_HOST) missing.push('DB_HOST');
  if (!SERVICE_CONFIG.DB_USER) missing.push('DB_USER');
  if (!SERVICE_CONFIG.DB_NAME) missing.push('DB_NAME');
  
  // Validate numeric values
  if (isNaN(SERVICE_CONFIG.PORT)) invalid.push('PORT (must be a number)');
  if (isNaN(SERVICE_CONFIG.DB_PORT)) invalid.push('DB_PORT (must be a number)');
  if (isNaN(LIMITS.DAILY_COST_LIMIT_USD)) invalid.push('DAILY_COST_LIMIT_USD (must be a number)');
  
  return {
    valid: missing.length === 0 && invalid.length === 0,
    missing,
    invalid
  };
}

/**
 * Returns a redacted version of the environment for logging
 * (strips out sensitive information like API keys)
 */
export function getRedactedEnvironment(): Record<string, any> {
  return {
    NODE_ENV: SERVICE_CONFIG.NODE_ENV,
    HOST: SERVICE_CONFIG.HOST,
    PORT: SERVICE_CONFIG.PORT,
    DB_HOST: SERVICE_CONFIG.DB_HOST,
    DB_PORT: SERVICE_CONFIG.DB_PORT,
    DB_NAME: SERVICE_CONFIG.DB_NAME,
    API_PREFIX: SERVICE_CONFIG.API_PREFIX,
    API_VERSION: SERVICE_CONFIG.API_VERSION,
    OPENAI_API_KEY: API_KEYS.OPENAI ? '[REDACTED]' : undefined,
    ANTHROPIC_API_KEY: API_KEYS.ANTHROPIC ? '[REDACTED]' : undefined,
    FEATURE_FLAGS: FEATURE_FLAGS,
    LIMITS: LIMITS
  };
}