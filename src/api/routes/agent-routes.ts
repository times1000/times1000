import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import db from '../../db';
import { logOperation } from '../services/logging-service';
import { Agent } from '../../core/Agent';
import { AgentCreationRequest, AgentStatus } from '../../types/agent';
import { BackgroundProcessor } from '../../background-processor';
import { asyncHandler } from '../middleware/error-middleware';
import { createError } from '../../utils/error-utils';
import { updateAgentStatus } from '../../utils/agent-utils';
import { sendSuccess, sendCreated } from '../../utils/api-utils';
import { eventService } from '../../services/event-service';
import { AGENT_STATUS, EVENTS } from '../../config/constants';

export default function(backgroundProcessor?: BackgroundProcessor) {
  const router = express.Router();

  // Get all agents
  router.get('/', asyncHandler(async (_req: express.Request, res: express.Response) => {
    const agents = await db.agents.getAllAgents();
    return sendSuccess(res, { agents });
  }));

  // Get agent by ID
  router.get('/:id', asyncHandler(async (req: express.Request, res: express.Response) => {
    const agent = await db.agents.getAgentById(req.params.id);
    
    if (!agent) {
      throw createError('Agent not found', 'AGENT_NOT_FOUND', { agentId: req.params.id }, 404);
    }
    
    return sendSuccess(res, agent);
  }));

  // Create a new agent with initial command
  router.post('/', asyncHandler(async (req: express.Request, res: express.Response) => {
    const { command, initialCapabilities, personalityProfile, settings } = req.body as AgentCreationRequest;
    
    if (!command) {
      throw createError('Command is required', 'COMMAND_REQUIRED', null, 400);
    }
    
    // Create a new agent ID
    const agentId = uuidv4();
    
    // Log the agent creation attempt
    await logOperation('agent_creation_started', {
      command,
      hasInitialCapabilities: !!initialCapabilities,
      hasPersonalityProfile: !!personalityProfile
    });
    
    // Create initial agent in database with temporary info
    const newAgent = {
      id: agentId,
      name: `Agent for: ${command.substring(0, 30)}${command.length > 30 ? '...' : ''}`,
      description: `Processing command: ${command}`,
      status: AgentStatus.PLAN_PENDING,
      capabilities: initialCapabilities || [],
      settings: settings || {},
      personalityProfile: personalityProfile || ''
    };
    
    const createdAgent = await db.agents.createAgent(newAgent);
    
    // Emit created event
    eventService.emit(EVENTS.AGENT.CREATED, createdAgent);
    
    // Queue the plan creation in the background
    if (backgroundProcessor) {
      // Use background processor to queue plan generation
      backgroundProcessor.queuePlanGeneration({
        agentId,
        command,
        isInitialPlan: true,
        requestId: uuidv4()
      });
      
      return sendCreated(
        res, 
        { agent: createdAgent }, 
        'Agent created. Plan generation has been queued and will be available shortly.'
      );
    } else {
      // Fallback if background processor is not available
      // Create a temporary agent instance for direct plan generation
      const tempAgent = new Agent(agentId);
      
      // Set optional properties
      if (initialCapabilities && Array.isArray(initialCapabilities)) {
        tempAgent.addCapabilities(initialCapabilities);
      }
      
      if (personalityProfile) {
        tempAgent.setPersonalityProfile(personalityProfile);
      }
      
      if (settings && typeof settings === 'object') {
        Object.entries(settings).forEach(([key, value]) => {
          tempAgent.setSetting(key, value);
        });
      }
      
      // Generate plan synchronously (legacy mode)
      const { plan, nameAndDescription } = await tempAgent.createWithCommand(command);
      
      // Update the agent in the database with the suggested name and description
      const updates = {
        name: nameAndDescription.name,
        description: nameAndDescription.description,
        status: AgentStatus.AWAITING_APPROVAL
      };
      
      await db.agents.updateAgent(agentId, updates);
      
      // Save the plan to the database
      const createdPlan = await db.plans.createPlan(plan);
      
      // Log successful creation
      await logOperation('agent_created_legacy', {
        agentId,
        planId: createdPlan.id,
        stepCount: createdPlan.steps.length
      });
      
      // Emit updated event
      eventService.emitAgentUpdated({ ...createdAgent, ...updates });
      
      // Emit plan created event
      eventService.emitPlanCreated(agentId, createdPlan.id);
      
      return sendCreated(res, {
        agent: { ...createdAgent, ...updates },
        plan: {
          planId: createdPlan.id,
          status: createdPlan.status,
          description: createdPlan.description,
          steps: createdPlan.steps
        }
      });
    }
  }));

  // Update an agent
  router.put('/:id', asyncHandler(async (req: express.Request, res: express.Response) => {
    const { name, description, status, capabilities, personalityProfile, settings } = req.body;
    const updates: Record<string, any> = {};
    
    if (name !== undefined) updates.name = name;
    if (description !== undefined) updates.description = description;
    if (status !== undefined) updates.status = status;
    if (capabilities !== undefined) updates.capabilities = capabilities;
    if (personalityProfile !== undefined) updates.personalityProfile = personalityProfile;
    if (settings !== undefined) updates.settings = settings;
    
    const updatedAgent = await db.agents.updateAgent(req.params.id, updates);
    
    // Emit agent updated event
    eventService.emitAgentUpdated(updatedAgent);
    
    return sendSuccess(res, updatedAgent);
  }));

  // Delete an agent
  router.delete('/:id', asyncHandler(async (req: express.Request, res: express.Response) => {
    const success = await db.agents.deleteAgent(req.params.id);
    
    if (!success) {
      throw createError('Agent not found', 'AGENT_NOT_FOUND', { agentId: req.params.id }, 404);
    }
    
    // Emit agent deleted event
    eventService.emit(EVENTS.AGENT.DELETED, req.params.id);
    
    return sendSuccess(res, { success: true });
  }));

  // Get current plan for an agent
  router.get('/:id/current-plan', asyncHandler(async (req: express.Request, res: express.Response) => {
    const plan = await db.plans.getCurrentPlanForAgent(req.params.id);
    
    if (!plan) {
      return sendSuccess(res, { hasPlan: false });
    }
    
    // Fetch follow-up suggestions if they exist
    let followUpSuggestions: any[] = [];
    try {
      // Get the plan ID to use
      const planId = (plan as any).id;
      
      // First check if the column exists to avoid errors
      const columnCheckSql = `
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'plans' AND COLUMN_NAME = 'follow_up_suggestions'
      `;
      const [columnsResult] = await db.pool.query(columnCheckSql, [process.env.DB_NAME || 'times1000']);
      
      // Only query for the column if it exists
      if (Array.isArray(columnsResult) && columnsResult.length > 0) {
        const followUpSql = 'SELECT follow_up_suggestions FROM plans WHERE id = ?';
        const [followUpResult] = await db.pool.query(followUpSql, [planId]);
        
        // Process result if available
        if (Array.isArray(followUpResult) && 
            followUpResult.length > 0 && 
            followUpResult[0] && 
            'follow_up_suggestions' in followUpResult[0]) {
          
          const suggestions = followUpResult[0].follow_up_suggestions;
          
          // Parse suggestions based on type
          if (suggestions) {
            followUpSuggestions = typeof suggestions === 'string' 
              ? JSON.parse(suggestions) 
              : suggestions;
          }
        }
      }
    } catch (err) {
      console.log('Could not retrieve follow-up suggestions:', err instanceof Error ? err.message : 'Unknown error');
      // Non-critical, we'll continue with empty suggestions
    }
    
    // Use the plan as any to safely access its properties
    const planAny = plan as any;
    
    const planResponse = {
      hasPlan: true,
      planId: planAny.id,
      hasFollowUp: followUpSuggestions.length > 0,
      followUpSuggestions,
      ...planAny
    };
    
    return sendSuccess(res, planResponse);
  }));

  // Send a command to an agent
  router.post('/:id/command', asyncHandler(async (req: express.Request, res: express.Response) => {
    const { command } = req.body;
    const agent = await db.agents.getAgentById(req.params.id);
    
    if (!agent) {
      throw createError('Agent not found', 'AGENT_NOT_FOUND', { agentId: req.params.id }, 404);
    }
    
    if (!command) {
      throw createError('Command is required', 'COMMAND_REQUIRED', null, 400);
    }
    
    // Log the command receipt
    await logOperation('command_received', {
      agentId: agent.id,
      command
    });
    
    // Update agent status to plan pending
    await updateAgentStatus(agent.id, AGENT_STATUS.PLAN_PENDING);
    
    if (backgroundProcessor) {
      // Queue plan generation in the background
      backgroundProcessor.queuePlanGeneration({
        agentId: agent.id,
        command,
        isInitialPlan: false,
        requestId: uuidv4()
      });
      
      return sendSuccess(res, {
        agentId: agent.id,
        message: 'Command received. Plan generation has been queued and will be available shortly.'
      });
    } else {
      // Fallback if background processor is not available
      // Create an Agent instance for direct plan generation
      const agentInstance = new Agent(agent.id, agent.name, agent.description);
      
      // Set capabilities if they exist
      if (agent.capabilities && Array.isArray(agent.capabilities)) {
        agentInstance.addCapabilities(agent.capabilities);
      }
      
      // Generate a plan with potential name/description update (legacy synchronous mode)
      const generatedPlan = await agentInstance.receiveCommand(command);
      
      // Save the plan to the database
      const createdPlan = await db.plans.createPlan(generatedPlan);
      
      // Update agent status and possibly name/description if they changed
      const updates: Record<string, any> = { status: AGENT_STATUS.AWAITING_APPROVAL };
      
      // If name or description changed, update them
      if (agentInstance.name !== agent.name) {
        updates.name = agentInstance.name;
      }
      
      if (agentInstance.description !== agent.description) {
        updates.description = agentInstance.description;
      }
      
      await db.agents.updateAgent(agent.id, updates);
      
      // Log plan creation
      await logOperation('plan_created_legacy', {
        agentId: agent.id,
        planId: createdPlan.id,
        stepCount: createdPlan.steps.length,
        nameUpdated: 'name' in updates,
        descriptionUpdated: 'description' in updates
      });
      
      // Emit plan created event
      eventService.emitPlanCreated(agent.id, createdPlan.id);
      
      // If name or description changed, emit update event
      if ('name' in updates || 'description' in updates) {
        eventService.emitAgentUpdated({
          ...agent,
          ...updates
        });
      }
      
      return sendSuccess(res, {
        planId: createdPlan.id,
        agentId: agent.id,
        status: createdPlan.status,
        description: createdPlan.description,
        steps: createdPlan.steps,
        nameUpdated: 'name' in updates ? updates.name : undefined,
        descriptionUpdated: 'description' in updates ? updates.description : undefined
      });
    }
  }));

  return router;
}