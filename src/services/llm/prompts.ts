/**
 * Centralized storage for all prompts used in the application
 * This makes it easier to edit and manage prompts without digging through code
 */

// System prompts
export const SYSTEM_PROMPTS = {
  PLAN_GENERATOR: 'You are an AI assistant that generates detailed plans for autonomous agents. Your plans should be thorough, logical, and follow a step-by-step approach.',
  AGENT_METADATA_CREATOR: 'You are an AI that creates concise, descriptive names and detailed descriptions for autonomous AI agents.',
  STEP_EXECUTOR: 'You are an AI assistant that executes steps in a plan with thoroughness and attention to detail.'
};

// Plan generation
export const PLAN_PROMPTS = {
  PLANNING_BASE: (command: string) => `Generate a detailed execution plan for the following command: "${command}"\n\n`,
  
  AGENT_CONTEXT: (name: string, capabilities: string[]) => {
    const capabilitiesString = capabilities && capabilities.length > 0 
      ? capabilities.join(', ') 
      : 'General planning and task execution';
      
    return `Agent Context:\n- Name: ${name}\n- Capabilities: ${capabilitiesString}\n`;
  },
  
  PERSONALITY_PROFILE: (profile: string) => profile ? `\nPersonality Profile:\n${profile}\n` : '',
  
  PLANNING_INSTRUCTIONS: `\nThe plan should include a clear description, reasoning, and step-by-step actions to accomplish the command. Each step should have a description and estimated time to complete. Consider dependencies between steps and potential error cases.`,
  
  NAME_DESCRIPTION_REQUEST: `\n\nBased on this command and plan, you should also suggest a concise, descriptive name for the agent and a detailed description of the agent's purpose and capabilities.`
};

// Agent metadata generation
export const METADATA_PROMPTS = {
  METADATA_FROM_PLAN: (plan: any) => `
    Based on the following plan details, generate a concise name and detailed description for an AI agent that would be responsible for executing this plan:
    
    Command: "${plan.command}"
    Plan Description: "${plan.description}"
    Plan Reasoning: "${plan.reasoning}"
    
    Steps (${plan.steps.length}):
    ${plan.steps.map((step: any, i: number) => `${i+1}. ${step.description}`).join('\n')}
    
    The agent name should be concise and descriptive. The description should explain the agent's purpose and capabilities.
    `
};

// Step execution
export const STEP_PROMPTS = {
  EXECUTION: (plan: any, step: any, stepNumber: number, agent: any = null) => {
    const agentInfo = agent ? `
Agent: ${agent.name}
Description: ${agent.description}
Capabilities: ${Array.isArray(agent.capabilities) ? agent.capabilities.join(', ') : 'General capabilities'}
` : '';

    return `
You are executing step ${stepNumber} of a plan to respond to this command: "${plan.command}"

${agentInfo}
Plan description: ${plan.description}
Current step: ${step.description}
${step.details ? `Details: ${step.details}` : ''}

Please execute this step and provide a detailed, thoughtful response as if you were the agent described above.
`;
  },
  
  CODE_EXECUTION_ADDITION: (mcpServicesString: string) => 
    `\nYou can write and execute code to complete this step.${mcpServicesString}`
};

// Follow-up suggestion generation
export const FOLLOWUP_PROMPTS = {
  SUGGESTIONS: (plan: any, agent: any) => `
You've just completed a plan with the following details:
- Command: "${plan.command}"
- Description: "${plan.description}"
- Agent name: ${agent.name}
- Agent description: ${agent.description}

Based on this completed task, what follow-up actions would be most valuable? Please suggest 2-4 specific follow-up actions that would extend or build upon the work that's been done.

Respond with a JSON array of follow-up suggestions, where each item is a clear, actionable suggestion phrased as a question.
`
};