import { Agent } from './Agent';
import { Plan, PlanImpl } from './Plan';
import { v4 as uuidv4 } from 'uuid';
import { openai } from '../utils/ai-client';
import * as llm from '../services/llm';
import { 
  SYSTEM_PROMPTS, 
  PLAN_PROMPTS, 
  METADATA_PROMPTS,
  DEFAULT_MODELS,
  TOKEN_LIMITS,
  TEMPERATURE_SETTINGS,
  OPERATION_NAMES,
  createPlanTool,
  createAgentMetadataTool
} from '../services/llm';

export interface AgentNameAndDescription {
  name: string;
  description: string;
}

export async function generatePlan(
  agent: Agent, 
  command: string, 
  includeNameAndDescription: boolean = false
): Promise<{ plan: Plan; agentNameAndDescription?: AgentNameAndDescription }> {
  try {
    // Build the prompt for the AI
    const prompt = buildPlanningPrompt(agent, command, includeNameAndDescription);
    
    // Using OpenAI-specific message format for tool calls
    const messages = [
      { 
        role: 'system' as const, 
        content: SYSTEM_PROMPTS.PLAN_GENERATOR
      },
      { role: 'user' as const, content: prompt }
    ];
    
    console.log(`Generating plan for agent ${agent.id} with command: "${command}"`);
    
    // Use centralized tool definition
    const planTool = createPlanTool(includeNameAndDescription);
    
    // Try to use the abstracted LLM service with tool execution
    try {
      // Use our abstracted service to allow tools to be used
      const response = await llm.chatCompletion(
        messages,
        {
          model: DEFAULT_MODELS.PLAN_GENERATION,
          temperature: TEMPERATURE_SETTINGS.PLAN_GENERATION,
          maxTokens: TOKEN_LIMITS.PLAN_GENERATION,
          executionStrategy: 'tools', 
          tools: [planTool]
        },
        {
          operation: OPERATION_NAMES.PLAN_GENERATION,
          agentId: agent.id
        }
      );
      
      // Extract tool call results from the response
      if (response.toolUsage && response.toolUsage.toolCalls > 0) {
        // Tool call was used, get the plan data from the tool response
        // For now, we're assuming the data is embedded in the content as JSON
        const planData = JSON.parse(response.content);
        return processPlanData(planData, agent, includeNameAndDescription);
      }
      
      // Fallback to OpenAI direct call if no tool results
      throw new Error('Tool execution did not return valid plan data');
    } catch (error) {
      console.log('Claude Code tool execution failed, falling back to OpenAI direct call:', error);
      
      // Send to the OpenAI API directly as fallback
      // We need to use the OpenAI client directly for tool calling support
      const response = await openai.chat.completions.create({
        model: DEFAULT_MODELS.PLAN_GENERATION,
        messages,
        temperature: TEMPERATURE_SETTINGS.PLAN_GENERATION,
        max_tokens: TOKEN_LIMITS.PLAN_GENERATION,
        tools: [{ type: 'function', function: planTool }],
        tool_choice: { type: 'function', function: { name: 'createPlan' } }
      });
    
    // Log the request to our LLM logging system
    if (response.usage) {
      await llm.logLLMRequest({
        provider: 'openai',
        model: DEFAULT_MODELS.PLAN_GENERATION,
        operation: OPERATION_NAMES.PLAN_GENERATION,
        prompt: JSON.stringify(messages),
        response: JSON.stringify(response.choices[0]?.message || '{}'),
        tokenUsage: {
          promptTokens: response.usage.prompt_tokens,
          completionTokens: response.usage.completion_tokens,
          totalTokens: response.usage.total_tokens
        },
        costUsd: llm.calculateCost('openai', 'gpt-4o', response.usage.prompt_tokens, response.usage.completion_tokens),
        durationMs: 0, // We don't have this info
        context: {
          agentId: agent.id
        }
      });
    }
    
    console.log(`Plan generation used ${response.usage?.prompt_tokens || 0} prompt tokens and ${response.usage?.completion_tokens || 0} completion tokens for agent ${agent.id}`);
    
    const toolCalls = response.choices[0]?.message.tool_calls;
    
    if (!toolCalls || toolCalls.length === 0) {
      throw new Error('Failed to generate plan: No tool calls in response');
    }
    
    const planData = JSON.parse(toolCalls[0].function.arguments);
    return processPlanData(planData, agent, includeNameAndDescription);
    }
  } catch (error: any) {
    console.error('Error generating plan:', error);
    throw new Error(`Failed to generate plan: ${error.message}`);
  }
}

/**
 * Process plan data from either Claude Code or OpenAI
 */
function processPlanData(
  planData: any, 
  agent: Agent, 
  includeNameAndDescription: boolean
): { plan: Plan; agentNameAndDescription?: AgentNameAndDescription } {
  try {
    // Create the plan
    const plan = new PlanImpl(
      uuidv4(),
      agent.id,
      agent.currentPlan?.command || "Unknown command",
      planData.description,
      planData.reasoning
    );
    
    // Add steps to the plan
    for (const stepData of planData.steps) {
      plan.addStep({
        description: stepData.description,
        estimatedDuration: stepData.estimatedDuration,
        details: stepData.details
      });
    }
    
    plan.hasFollowUp = planData.hasFollowUp;
    plan.followUpSuggestions = planData.followUpSuggestions;
    
    // Extract agent name and description if available
    let agentNameAndDescription: AgentNameAndDescription | undefined;
    
    if (includeNameAndDescription) {
      const agentName = 'agentName' in planData ? planData.agentName : undefined;
      const agentDescription = 'agentDescription' in planData ? planData.agentDescription : undefined;
      
      if (agentName && agentDescription) {
        agentNameAndDescription = {
          name: agentName,
          description: agentDescription
        };
      }
    }
    
    return { 
      plan,
      agentNameAndDescription
    };
  } catch (error) {
    console.error('Error processing plan data:', error);
    throw new Error('Failed to process plan data');
  }
}

/**
 * If the initial agent name/description generation fails, this function
 * can separately generate those values from an existing plan
 */
export async function generateAgentMetadataFromPlan(plan: Plan): Promise<AgentNameAndDescription> {
  try {
    // Create prompt for metadata generation
    const prompt = METADATA_PROMPTS.METADATA_FROM_PLAN(plan);
    
    // We still need to use the OpenAI API directly for tool calling
    const response = await openai.chat.completions.create({
      model: DEFAULT_MODELS.AGENT_METADATA,
      messages: [
        { 
          role: 'system' as const, 
          content: SYSTEM_PROMPTS.AGENT_METADATA_CREATOR
        },
        { role: 'user' as const, content: prompt }
      ],
      temperature: TEMPERATURE_SETTINGS.PLAN_GENERATION,
      max_tokens: TOKEN_LIMITS.AGENT_METADATA,
      tools: [
        {
          type: 'function',
          function: createAgentMetadataTool
        }
      ],
      tool_choice: { type: 'function', function: { name: 'createAgentMetadata' } }
    });
    
    // Log the request to our LLM logging system
    if (response.usage) {
      await llm.logLLMRequest({
        provider: 'openai',
        model: DEFAULT_MODELS.AGENT_METADATA,
        operation: OPERATION_NAMES.AGENT_METADATA,
        prompt: prompt,
        response: JSON.stringify(response.choices[0]?.message || '{}'),
        tokenUsage: {
          promptTokens: response.usage.prompt_tokens,
          completionTokens: response.usage.completion_tokens,
          totalTokens: response.usage.total_tokens
        },
        costUsd: llm.calculateCost('openai', 'gpt-4o', response.usage.prompt_tokens, response.usage.completion_tokens),
        durationMs: 0, // We don't have this info
        context: {
          planId: plan.id
        }
      });
    }
    
    const toolCalls = response.choices[0]?.message.tool_calls;
    
    if (!toolCalls || toolCalls.length === 0) {
      throw new Error('Failed to generate agent metadata');
    }
    
    const metadataResult = JSON.parse(toolCalls[0].function.arguments);
    
    return {
      name: metadataResult.name,
      description: metadataResult.description
    };
  } catch (error: any) {
    console.error('Error generating agent metadata:', error);
    // Return fallback values in case of error
    return {
      name: `Plan Executor for: ${plan.command.substring(0, 30)}${plan.command.length > 30 ? '...' : ''}`,
      description: `Agent responsible for executing the plan: ${plan.description}`
    };
  }
}


function buildPlanningPrompt(agent: Agent, command: string, includeNameAndDescription: boolean = false): string {
  let prompt = PLAN_PROMPTS.PLANNING_BASE(command);
  
  prompt += PLAN_PROMPTS.AGENT_CONTEXT(agent.name, agent.capabilities);
  
  prompt += PLAN_PROMPTS.PERSONALITY_PROFILE(agent.personalityProfile);
  
  prompt += PLAN_PROMPTS.PLANNING_INSTRUCTIONS;
  
  if (includeNameAndDescription) {
    prompt += PLAN_PROMPTS.NAME_DESCRIPTION_REQUEST;
  }
  
  return prompt;
}