// Core exports
export { Agent } from './core/Agent';
export { PlanImpl as Plan } from './core/Plan';
export type { PlanStep, PlanStatus, StepStatus } from './core/Plan';
export { generatePlan } from './core/PlanGenerator';

// Type exports
export { AgentStatus } from './types/agent';
export type { AgentConfig, AgentData, AgentStats, AgentCreationRequest } from './types/agent';

// Utilities
export { openai, chatWithAI, extractInfoFromText, generateEmbedding } from './utils/ai-client';
export { 
  fileExists, 
  ensureDirectory, 
  readJsonFile, 
  writeJsonFile, 
  listFiles 
} from './utils/file-helpers';

// Version information
export const VERSION = '0.1.0';
export const AUTHOR = 'Claude AI';

// Main library description
/**
 * *1000 - A semi-autonomous AI agent framework
 * 
 * This library provides tools for creating AI agents that can:
 * 1. Generate plans for tasks based on user commands
 * 2. Wait for human approval before execution
 * 3. Execute plans step by step
 * 4. Generate follow-up suggestions
 * 
 * The framework uses a unified agent architecture that:
 * - Automatically generates agent names and descriptions
 * - Adapts to any task with configurable capabilities
 * - Creates detailed execution plans
 * - Updates itself as it takes on new tasks
 * 
 * @example
 * ```typescript
 * import { Agent } from '*1000';
 * 
 * // Create a new agent with just an ID
 * const agent = new Agent('agent-1');
 * 
 * // Listen for plan creation events
 * agent.on('planCreated', (plan) => {
 *   console.log('New plan created:', plan.description);
 * });
 * 
 * // Create a plan from a command (with name/description generation)
 * const result = await agent.createWithCommand(
 *   'Analyze this text and identify key themes'
 * );
 * 
 * console.log('Agent name:', agent.name);
 * console.log('Agent description:', agent.description);
 * console.log('Plan:', result.plan);
 * ```
 */