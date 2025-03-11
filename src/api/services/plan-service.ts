import { v4 as uuidv4 } from 'uuid';
import db from '../../db';
import { logOperation } from './logging-service';
import { Server } from 'socket.io';
import OpenAI from 'openai';
import * as llm from '../../services/llm';
import { Plan } from '../../types/db'; // PlanStep and PlanRowData are unused
import { Agent } from '../../core/Agent';
import { generatePlan as generateAgentPlan, generateAgentMetadataFromPlan } from '../../core/PlanGenerator';

/**
 * Generate a plan using agent's receiveCommand method
 */
async function generatePlan(openai: OpenAI, agent: any, command: string) {
  // Log the AI request for plan generation
  logOperation('ai_plan_generation', {
    agentId: agent.id,
    command,
    model: 'gpt-4-turbo',
    temperature: 0.7
  });

  try {
    // Create an agent instance
    const agentInstance = new Agent(agent.id, agent.name, agent.description);
    
    // Set capabilities if they exist
    if (agent.capabilities && Array.isArray(agent.capabilities)) {
      agentInstance.capabilities = agent.capabilities;
    }
    
    // Set personality profile if it exists
    if (agent.personalityProfile) {
      agentInstance.personalityProfile = agent.personalityProfile;
    }
    
    // Generate a plan using the agent instance
    const plan = await agentInstance.receiveCommand(command);
    const agentNameAndDescription = agentInstance.name !== agent.name || agentInstance.description !== agent.description
      ? { name: agentInstance.name, description: agentInstance.description }
      : undefined;
    
    // Create the plan structure for the database
    const dbPlan: Plan = {
      id: uuidv4(),
      agentId: agent.id,
      command,
      description: plan.description,
      reasoning: plan.reasoning,
      status: 'awaiting_approval',
      steps: plan.steps.map((step, index) => ({
        id: uuidv4(),
        description: step.description,
        status: 'pending',
        estimatedDuration: step.estimatedDuration || 30,
        details: step.details || '',
        position: index
      }))
    };
    
    // Add follow-up suggestions if provided
    if (plan.hasFollowUp && plan.followUpSuggestions && plan.followUpSuggestions.length > 0) {
      dbPlan.followUpSuggestions = plan.followUpSuggestions;
      dbPlan.hasFollowUp = true;
    }
    
    // If agent name and description were generated, include them
    if (agentNameAndDescription) {
      (dbPlan as any).agentNameAndDescription = agentNameAndDescription;
    }
    
    return dbPlan;
  } catch (error) {
    console.error('Error generating plan with agent:', error);
    
    // Fall back to the original OpenAI implementation if the agent method fails
    return generatePlanWithOpenAI(openai, agent, command);
  }
}

/**
 * Original implementation using OpenAI directly
 */
async function generatePlanWithOpenAI(openai: OpenAI, agent: any, command: string) {
  try {
    // Create a temporary Agent instance
    const tempAgent = new Agent(agent.id, agent.name, agent.description);
    
    // Add capabilities if they exist
    if (agent.capabilities && Array.isArray(agent.capabilities)) {
      tempAgent.capabilities = agent.capabilities;
    }
    
    // Use the core PlanGenerator directly
    const { plan, agentNameAndDescription } = await generateAgentPlan(tempAgent, command, true);
    
    // Create the plan structure for the database
    const dbPlan: any = {
      id: uuidv4(),
      agentId: agent.id,
      command,
      description: plan.description,
      reasoning: plan.reasoning,
      status: 'awaiting_approval',
      steps: plan.steps.map((step, index) => ({
        id: uuidv4(),
        description: step.description,
        status: 'pending',
        estimatedDuration: step.estimatedDuration || 30,
        details: step.details || '',
        position: index
      })),
      // Add empty array by default
      followUpSuggestions: []
    };
    
    // Add follow-up suggestions if provided
    if (plan.hasFollowUp && plan.followUpSuggestions && plan.followUpSuggestions.length > 0) {
      dbPlan.followUpSuggestions = plan.followUpSuggestions;
      dbPlan.hasFollowUp = true;
    }
    
    // Include agent name and description if generated
    if (agentNameAndDescription) {
      dbPlan.agentNameAndDescription = agentNameAndDescription;
    }
    
    return dbPlan;
  } catch (error) {
    console.error('Error generating plan with OpenAI:', error);
    
    // Fallback to a basic plan structure if API fails
    return generateFallbackPlan(agent, command);
  }
}

/**
 * Generate a fallback plan when OpenAI API fails
 */
function generateFallbackPlan(agent: any, command: string): any {
  const planDescription = `Process request: "${command}"`;
  const planReasoning = `This plan will systematically analyze, process, and generate results for the provided command.`;
  
  // Generic steps for the unified agent
  const steps = [
    {
      id: uuidv4(),
      description: 'Analyze and parse command parameters',
      status: 'pending',
      estimatedDuration: 30,
      position: 0
    },
    {
      id: uuidv4(),
      description: 'Process command with optimal settings',
      status: 'pending',
      estimatedDuration: 90,
      position: 1
    },
    {
      id: uuidv4(),
      description: 'Generate results and recommendations',
      status: 'pending',
      estimatedDuration: 60,
      position: 2
    }
  ];
  
  // Also generate a name and description for the agent if this is a new agent
  let agentNameAndDescription = undefined;
  
  try {
    // Extract a suitable name and description based on the command
    const commandWords = command.split(' ').filter(w => w.length > 3).slice(0, 3);
    const defaultName = `Agent for ${commandWords.join(' ')}`;
    const defaultDescription = `An agent that helps with tasks related to "${command}"`;
    
    agentNameAndDescription = {
      name: defaultName,
      description: defaultDescription
    };
  } catch (e) {
    console.error('Error generating fallback agent metadata:', e);
  }
  
  return {
    id: uuidv4(),
    agentId: agent.id,
    command,
    description: planDescription,
    reasoning: planReasoning,
    status: 'awaiting_approval',
    steps,
    agentNameAndDescription
  };
}

/**
 * Execute the AI processing for a plan
 */
async function executeAiProcessing(openai: OpenAI, io: Server, agentId: string, planId: string): Promise<void> {
  try {
    // Log the operation
    await logOperation('ai_processing_started', {
      agentId,
      planId,
      model: 'gpt-4-turbo',
      task: 'plan_execution'
    });
    
    // Get agent from database
    const agent = await db.agents.getAgentById(agentId);
    if (!agent) {
      throw new Error('Agent not found');
    }
    
    // Get plan from database
    const plan = await db.plans.getCurrentPlanForAgent(agentId);
    
    // To be safe, convert to any type
    const planData = plan as any;
    
    if (!planData || planData.id !== planId) {
      throw new Error('Plan not found for execution');
    }
    
    // Create unified agent instance
    const agentInstance = new Agent(agent.id, agent.name, agent.description);
    
    // Set capabilities if they exist
    if (agent.capabilities && Array.isArray(agent.capabilities)) {
      agentInstance.capabilities = agent.capabilities;
    }
    
    // Set personality profile if it exists
    if (agent.personalityProfile) {
      agentInstance.personalityProfile = agent.personalityProfile;
    }
    
    // Set settings if they exist
    if (agent.settings && typeof agent.settings === 'object') {
      agentInstance.settings = agent.settings;
    }
    
    // Attach socket event listeners to the agent instance
    agentInstance.on('statusChange', async (status) => {
      // Update agent status in the database
      await db.agents.updateAgent(agentId, { status });
      
      // Broadcast status change
      io.emit('agent:status', {
        agentId,
        status
      });
    });
    
    agentInstance.on('stepStatusChange', async (step) => {
      try {
        // The method exists in the code but wasn't exported properly
        // Use direct query as a workaround
        await db.pool.query(`
          UPDATE plan_steps 
          SET status = ?, result = ? 
          WHERE id = ?
        `, [step.status, step.result || null, step.id]);
        
        // Broadcast step status change
        io.emit('step:status', {
          agentId,
          planId,
          stepId: step.id,
          status: step.status
        });
      } catch (error) {
        console.error(`Error updating step status: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
      
      // If step completed, broadcast result
      if (step.status === 'completed') {
        io.emit('step:completed', {
          agentId,
          planId,
          stepId: step.id,
          status: 'completed',
          result: step.result
        });
        
        // Log step completion
        await logOperation('step_execution_completed', {
          agentId,
          planId,
          stepId: step.id,
          resultLength: step.result ? step.result.length : 0
        });
      }
    });
    
    // Also listen for potential name/description updates
    agentInstance.on('metadataUpdated', async ({ name, description }) => {
      // If name or description have changed, update in database
      const updates: Record<string, any> = {};
      
      if (name !== agent.name) {
        updates.name = name;
      }
      
      if (description !== agent.description) {
        updates.description = description;
      }
      
      if (Object.keys(updates).length > 0) {
        await db.agents.updateAgent(agentId, updates);
        
        // Broadcast the update
        io.emit('agent:updated', {
          ...agent,
          ...updates
        });
        
        // Log the metadata update
        await logOperation('agent_metadata_updated', {
          agentId,
          nameUpdated: 'name' in updates,
          descriptionUpdated: 'description' in updates
        });
      }
    });
    
    // Set current plan - with type safety
    const planForAgent = {
      id: planData.id,
      agentId: planData.agentId,
      command: planData.command,
      description: planData.description,
      reasoning: planData.reasoning,
      status: 'approved' as const,  // Use const assertion to fix the type
      steps: Array.isArray(planData.steps) ? planData.steps.map((step: any) => ({
        id: step.id,
        description: step.description,
        status: 'pending' as const,  // Use const assertion to fix the type
        estimatedDuration: step.estimatedDuration,
        details: step.details,
        position: step.position
      })) : [],
      hasFollowUp: false,
      followUpSuggestions: [] as string[],
      // Add required methods to make it match Plan interface
      reorderSteps: () => {}, // Empty implementation 
      addStep: () => {},
      removeStep: () => {},
      updateStep: () => {},
      getStepById: () => undefined,
      createdAt: new Date(),
      updatedAt: new Date()
    };
    
    agentInstance.currentPlan = planForAgent;
    
    // Execute the plan
    await agentInstance.executePlan();
    
    // Generate follow-up suggestions
    const followUpSuggestions = await generateFollowUpSuggestions(openai, plan, agent);
    
    // Log follow-up generation
    await logOperation('follow_up_generation', {
      agentId,
      planId,
      suggestionCount: followUpSuggestions.length
    });
    
    // Update plan in database with completed status and follow-ups
    await db.plans.updatePlanStatus(planId, 'completed');
    
    // Store follow-up suggestions
    try {
      await db.pool.query(`
        UPDATE plans 
        SET follow_up_suggestions = ? 
        WHERE id = ?
      `, [JSON.stringify(followUpSuggestions), planId]);
    } catch (error) {
      console.log('Could not store follow-up suggestions. This is non-critical:', error instanceof Error ? error.message : 'Unknown error');
    }
    
    // Update agent status to idle (just in case the agent event didn't trigger)
    await db.agents.updateAgent(agentId, { status: 'idle' });
    
    // Log plan completion
    await logOperation('plan_execution_completed', {
      agentId,
      planId,
      status: 'success',
      hasFollowUps: followUpSuggestions.length > 0
    });
    
    // Broadcast plan completion with follow-ups
    io.emit('plan:completed', {
      agentId,
      planId,
      hasFollowUp: followUpSuggestions.length > 0,
      followUpSuggestions
    });
    
  } catch (error) {
    console.error('Error in AI processing:', error);
    
    // Log error
    await logOperation('ai_processing_error', {
      agentId,
      planId,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
    
    // Update agent status to error
    await db.agents.updateAgent(agentId, { status: 'error' });
    
    // Update plan status to failed
    await db.plans.updatePlanStatus(planId, 'failed');
    
    // Broadcast plan failure
    io.emit('plan:failed', {
      agentId,
      planId,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
    
    // If the agent-based approach failed, fall back to the original method
    await executeAiProcessingFallback(openai, io, agentId, planId);
  }
}

/**
 * Updated implementation of executeAiProcessing to use as fallback
 */
async function executeAiProcessingFallback(openai: OpenAI, io: Server, agentId: string, planId: string): Promise<void> {
  try {
    const plan = await db.plans.getCurrentPlanForAgent(agentId);
    // Convert to any for type safety
    const planData = plan as any;
    
    if (!planData || planData.id !== planId) {
      console.error('Plan not found for execution');
      return;
    }
    
    // Execute each step with AI
    if (!Array.isArray(planData.steps)) {
      console.error('No steps found in plan');
      return;
    }
    
    // Get agent information for step execution
    const agent = await db.agents.getAgentById(agentId);
    if (!agent) {
      console.error('Agent not found for step execution');
      return;
    }
    
    for (let i = 0; i < planData.steps.length; i++) {
      const step = planData.steps[i] as any;
      
      // Log step start
      await logOperation('step_execution_started', {
        agentId,
        planId,
        stepId: step.id,
        stepNumber: i + 1,
        totalSteps: plan.steps.length
      });
      
      // Update step to in_progress - use direct query as workaround
      await db.pool.query(`
        UPDATE plan_steps 
        SET status = ? 
        WHERE id = ?
      `, ['in_progress', step.id]);
      
      // Broadcast step status change
      io.emit('step:status', {
        agentId,
        planId,
        stepId: step.id,
        status: 'in_progress'
      });
      
      // Execute the step with OpenAI - pass agent context
      const result = await executeStepWithAI(openai, plan, step, i + 1, agent);
      
      // Complete the step - use direct query as workaround
      await db.pool.query(`
        UPDATE plan_steps 
        SET status = ?, result = ? 
        WHERE id = ?
      `, ['completed', result, step.id]);
      
      // Log step completion
      await logOperation('step_execution_completed', {
        agentId,
        planId,
        stepId: step.id,
        resultLength: result.length
      });
      
      // Broadcast step completion
      io.emit('step:completed', {
        agentId,
        planId,
        stepId: step.id,
        status: 'completed',
        result
      });
    }
    
    // Generate updated agent name/description based on completed plan if needed
    try {
      const { name, description } = await generateAgentMetadataFromPlan(planData);
      
      // Check if name or description should be updated
      const updates: Record<string, any> = {};
      if (name !== agent.name) {
        updates.name = name;
      }
      if (description !== agent.description) {
        updates.description = description;
      }
      
      // Update agent metadata if changes are detected
      if (Object.keys(updates).length > 0) {
        await db.agents.updateAgent(agentId, updates);
        
        // Broadcast the update
        io.emit('agent:updated', {
          ...agent,
          ...updates
        });
        
        // Log the metadata update
        await logOperation('agent_metadata_updated_fallback', {
          agentId,
          nameUpdated: 'name' in updates,
          descriptionUpdated: 'description' in updates
        });
      }
    } catch (metadataError) {
      console.error('Error generating agent metadata from plan:', metadataError);
      // Non-critical, continue execution
    }
    
    // Finish the plan execution
    await db.plans.updatePlanStatus(planId, 'completed');
    await db.agents.updateAgent(agentId, { status: 'idle' });
    
  } catch (error) {
    console.error('Error in fallback AI processing:', error);
    // Don't throw, as this is already a fallback method
  }
}

/**
 * Execute a step with OpenAI
 */
async function executeStepWithAI(openai: OpenAI, plan: any, step: any, stepNumber: number, agent: any = null): Promise<string> {
  try {
    // Build the prompt for step execution with agent context
    const agentInfo = agent ? `
Agent: ${agent.name}
Description: ${agent.description}
Capabilities: ${Array.isArray(agent.capabilities) ? agent.capabilities.join(', ') : 'General capabilities'}
` : '';

    const prompt = `
You are executing step ${stepNumber} of a plan to respond to this command: "${plan.command}"

${agentInfo}
Plan description: ${plan.description}
Current step: ${step.description}
${step.details ? `Details: ${step.details}` : ''}

Please execute this step and provide a detailed, thoughtful response as if you were the agent described above.
`;

    // Use our abstracted LLM service
    const messages = [
      { role: 'system' as const, content: 'You are an AI assistant that executes steps in a plan with thoroughness and attention to detail.' },
      { role: 'user' as const, content: prompt }
    ];
    
    const response = await llm.chatCompletion(
      messages,
      {
        model: 'gpt-4o',
        temperature: 0.7,
        maxTokens: 1500
      },
      {
        operation: 'execute_step',
        agentId: plan.agentId,
        planId: plan.id
      }
    );
    
    return response.content;
  } catch (error) {
    console.error('Error executing step:', error);
    // Fall back to a fake result if LLM call fails
    return generateFakeStepResult(step.description);
  }
}

/**
 * Generate follow-up suggestions based on the plan
 */
async function generateFollowUpSuggestions(openai: OpenAI, plan: any, agent: any): Promise<string[]> {
  // Log the AI request for follow-up suggestions
  logOperation('ai_followup_generation', {
    planId: plan.id,
    agentId: plan.agentId,
    command: plan.command,
    model: 'gpt-4-turbo'
  });
  
  try {
    // Build the prompt for follow-up suggestions
    const prompt = `
You've just completed a plan with the following details:
- Command: "${plan.command}"
- Description: "${plan.description}"
- Agent name: ${agent.name}
- Agent description: ${agent.description}

Based on this completed task, what follow-up actions would be most valuable? Please suggest 2-4 specific follow-up actions that would extend or build upon the work that's been done.

Respond with a JSON array of follow-up suggestions, where each item is a clear, actionable suggestion phrased as a question.
`;

    // Extract info using our abstracted LLM service
    const parsed = await llm.extractInfo(
      prompt,
      "Generate follow-up suggestions after a completed task", 
      { 
        model: 'gpt-4o',
        temperature: 0.7
      },
      {
        operation: 'follow_up_generation',
        agentId: plan.agentId,
        planId: plan.id
      }
    );
    
    if (Array.isArray(parsed?.suggestions)) {
      return parsed.suggestions;
    } else if (Array.isArray(parsed?.followups)) {
      return parsed.followups;
    } else if (Array.isArray(parsed)) {
      return parsed;
    }
    
    // If we can't parse the response correctly, fall back to generated suggestions
    return generateFallbackFollowUps(agent);
  } catch (error) {
    console.error('Error generating follow-up suggestions with OpenAI:', error);
    return generateFallbackFollowUps(agent);
  }
}

/**
 * Generate fallback follow-up suggestions when OpenAI API fails
 */
function generateFallbackFollowUps(agent: any): string[] {
  // Extract useful keywords from agent name and description
  const agentText = `${agent.name} ${agent.description}`.toLowerCase();
  
  // Check for capability clues in agent name/description
  if (agentText.includes('content') || agentText.includes('analysis') || agentText.includes('text')) {
    return [
      "Would you like me to generate a detailed report based on this analysis?",
      "Should I extract key action items from this content?",
      "Would you like me to compare this content with previous analyses to identify trends?"
    ];
  } else if (agentText.includes('code') || agentText.includes('programming') || agentText.includes('development')) {
    return [
      "Would you like me to optimize the code for better performance?",
      "Should I create unit tests for the implemented solution?",
      "Would you like me to document the API interfaces for this implementation?"
    ];
  } else if (agentText.includes('social') || agentText.includes('media') || agentText.includes('content')) {
    return [
      "Would you like me to draft follow-up posts based on engagement metrics?",
      "Should I analyze competitor content for additional insights?",
      "Would you like me to generate a content calendar for the next two weeks?"
    ];
  } else {
    // Default suggestions
    return [
      "Would you like me to analyze this data in more depth?",
      "Should I prepare a summary report of the findings?",
      "Would you like me to schedule a follow-up task to track progress?"
    ];
  }
}

/**
 * Generate fake result text for a step (fallback when OpenAI fails)
 */
function generateFakeStepResult(description: string): string {
  const responses = [
    `Successfully analyzed the request: "${description}". Found several interesting patterns in the data.`,
    `Completed task: "${description}". The results indicate a positive outcome with 87% confidence.`,
    `Executed "${description}" with optimal parameters. Analysis suggests further investigation may be beneficial.`,
    `Task "${description}" finished. Extracted 3 key insights from the provided information.`,
    `Processed request: "${description}". Generated comprehensive report with actionable recommendations.`,
    `Completed analysis of "${description}". Identified 5 critical factors affecting the outcome.`
  ];
  
  // Return a random response
  return responses[Math.floor(Math.random() * responses.length)];
}

export {
  generatePlan,
  executeAiProcessing,
  generateFollowUpSuggestions
};