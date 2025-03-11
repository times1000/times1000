import { Agent } from './Agent';
import { Plan, PlanImpl } from './Plan';
import { v4 as uuidv4 } from 'uuid';
import { openai } from '../utils/ai-client';
import * as llm from '../services/llm';

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
        content: 'You are an AI assistant that generates detailed plans for autonomous agents. Your plans should be thorough, logical, and follow a step-by-step approach.'
      },
      { role: 'user' as const, content: prompt }
    ];
    
    console.log(`Generating plan for agent ${agent.id} with command: "${command}"`);
    
    // Define the tool for creating plans
    const planTool = {
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
    };
    
    // Try to use the abstracted LLM service with tool execution
    try {
      // Use our abstracted service to allow tools to be used
      const response = await llm.chatCompletion(
        messages,
        {
          model: 'gpt-4o',
          temperature: 0.7,
          maxTokens: 2000,
          executionStrategy: 'tools', 
          tools: [planTool]
        },
        {
          operation: 'generate_plan',
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
        model: 'gpt-4o',
        messages,
        temperature: 0.7,
        max_tokens: 2000,
        tools: [{ type: 'function', function: planTool }],
        tool_choice: { type: 'function', function: { name: 'createPlan' } }
      });
    
    // Log the request to our LLM logging system
    if (response.usage) {
      await llm.logLLMRequest({
        provider: 'openai',
        model: 'gpt-4o',
        operation: 'generate_plan',
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
    const prompt = `
    Based on the following plan details, generate a concise name and detailed description for an AI agent that would be responsible for executing this plan:
    
    Command: "${plan.command}"
    Plan Description: "${plan.description}"
    Plan Reasoning: "${plan.reasoning}"
    
    Steps (${plan.steps.length}):
    ${plan.steps.map((step, i) => `${i+1}. ${step.description}`).join('\n')}
    
    The agent name should be concise and descriptive. The description should explain the agent's purpose and capabilities.
    `;
    
    // We still need to use the OpenAI API directly for tool calling
    const response = await openai.chat.completions.create({
      model: 'gpt-4o',
      messages: [
        { 
          role: 'system' as const, 
          content: 'You are an AI that creates concise, descriptive names and detailed descriptions for autonomous AI agents.'
        },
        { role: 'user' as const, content: prompt }
      ],
      temperature: 0.7,
      max_tokens: 300,
      tools: [
        {
          type: 'function',
          function: {
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
          }
        }
      ],
      tool_choice: { type: 'function', function: { name: 'createAgentMetadata' } }
    });
    
    // Log the request to our LLM logging system
    if (response.usage) {
      await llm.logLLMRequest({
        provider: 'openai',
        model: 'gpt-4o',
        operation: 'generate_agent_metadata',
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
  let prompt = `Generate a detailed execution plan for the following command: "${command}"\n\n`;
  
  prompt += `Agent Context:\n`;
  prompt += `- Name: ${agent.name}\n`;
  
  // Add capabilities context
  if (agent.capabilities && agent.capabilities.length > 0) {
    prompt += `- Capabilities: ${agent.capabilities.join(', ')}\n`;
  } else {
    prompt += `- Capabilities: General planning and task execution\n`;
  }
  
  if (agent.personalityProfile) {
    prompt += `\nPersonality Profile:\n${agent.personalityProfile}\n`;
  }
  
  prompt += `\nThe plan should include a clear description, reasoning, and step-by-step actions to accomplish the command. Each step should have a description and estimated time to complete. Consider dependencies between steps and potential error cases.`;
  
  if (includeNameAndDescription) {
    prompt += `\n\nBased on this command and plan, you should also suggest a concise, descriptive name for the agent and a detailed description of the agent's purpose and capabilities.`;
  }
  
  return prompt;
}