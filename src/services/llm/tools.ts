/**
 * Centralized definitions for all tool functions used by LLM services
 * This makes it easier to maintain consistent tool interfaces
 */
import { ToolFunction } from './types';

/**
 * Tool definition for creating a detailed plan
 */
export const createPlanTool = (includeNameAndDescription: boolean = false): ToolFunction => ({
  name: 'createPlan',
  description: 'Create a detailed execution plan with steps',
  parameters: {
    type: 'object',
    properties: {
      description: {
        type: 'string',
        description: 'A brief summary of what the plan will accomplish'
      },
      reasoning: {
        type: 'string',
        description: 'The reasoning behind the plan structure and approach'
      },
      steps: {
        type: 'array',
        description: 'The step-by-step execution plan',
        items: {
          type: 'object',
          properties: {
            description: {
              type: 'string',
              description: 'A description of what this step accomplishes'
            },
            estimatedDuration: {
              type: 'number',
              description: 'Estimated time to complete this step in seconds'
            },
            details: {
              type: 'string',
              description: 'Additional details about how this step will be executed'
            }
          },
          required: ['description']
        }
      },
      hasFollowUp: {
        type: 'boolean',
        description: 'Whether this plan will likely need follow-up actions'
      },
      followUpSuggestions: {
        type: 'array',
        description: 'Potential follow-up actions after plan completion',
        items: {
          type: 'string'
        }
      },
      agentName: includeNameAndDescription ? {
        type: 'string',
        description: 'A concise, descriptive name for the agent based on its purpose and capabilities'
      } : undefined,
      agentDescription: includeNameAndDescription ? {
        type: 'string',
        description: 'A detailed description of what this agent does and its primary function'
      } : undefined
    },
    required: includeNameAndDescription 
      ? ['description', 'reasoning', 'steps', 'hasFollowUp', 'agentName', 'agentDescription'] 
      : ['description', 'reasoning', 'steps', 'hasFollowUp']
  }
});

/**
 * Tool definition for creating agent metadata
 */
export const createAgentMetadataTool: ToolFunction = {
  name: 'createAgentMetadata',
  description: 'Create a name and description for an agent based on its plan',
  parameters: {
    type: 'object',
    properties: {
      name: {
        type: 'string',
        description: 'A concise, descriptive name for the agent based on its purpose'
      },
      description: {
        type: 'string',
        description: 'A detailed description of what this agent does and its primary function'
      }
    },
    required: ['name', 'description']
  }
};

/**
 * Tool definition for executing a plan step
 */
export const executeStepTool: ToolFunction = {
  name: 'executeStep',
  description: 'Execute a single step in a plan',
  parameters: {
    type: 'object',
    properties: {
      result: {
        type: 'string',
        description: 'The detailed result of executing this step'
      },
      status: {
        type: 'string',
        description: 'The status of the step after execution',
        enum: ['completed', 'failed', 'partial']
      },
      notes: {
        type: 'string',
        description: 'Optional notes about the execution process or results'
      }
    },
    required: ['result', 'status']
  }
};

/**
 * Tool definition for generating follow-up suggestions
 */
export const generateFollowUpsTool: ToolFunction = {
  name: 'generateFollowUps',
  description: 'Generate follow-up suggestions after completing a plan',
  parameters: {
    type: 'object',
    properties: {
      suggestions: {
        type: 'array',
        description: 'List of follow-up suggestions as questions',
        items: {
          type: 'string'
        }
      }
    },
    required: ['suggestions']
  }
};

/**
 * Tool definition for data extraction
 */
export const extractDataTool: ToolFunction = {
  name: 'extractData',
  description: 'Extract structured data from text content',
  parameters: {
    type: 'object',
    properties: {
      data: {
        type: 'object',
        description: 'The extracted data in structured format'
      }
    },
    required: ['data']
  }
};