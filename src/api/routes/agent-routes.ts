import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import db from '../../db';
// import { generatePlan } from '../services/plan-service';
import { logOperation } from '../services/logging-service';
import { Server } from 'socket.io';
import OpenAI from 'openai';
import { Agent } from '../../core/Agent';
import { AgentCreationRequest } from '../../types/agent';

export default function(io: Server, _openai: OpenAI) {
  const router = express.Router();

  // Get all agents
  router.get('/', async (_req: express.Request, res: express.Response) => {
    try {
      const agents = await db.agents.getAllAgents();
      res.json({ agents });
    } catch (error) {
      console.error('Error fetching agents:', error);
      res.status(500).json({ error: 'Failed to fetch agents' });
    }
  });

  // Get agent by ID
  router.get('/:id', async (req: express.Request, res: express.Response) => {
    try {
      const agent = await db.agents.getAgentById(req.params.id);
      
      if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
      }
      
      res.json(agent);
    } catch (error) {
      console.error(`Error fetching agent ${req.params.id}:`, error);
      res.status(500).json({ error: 'Failed to fetch agent' });
    }
  });

  // Create a new agent with initial command
  router.post('/', async (req: express.Request, res: express.Response) => {
    try {
      const { command, initialCapabilities, personalityProfile, settings } = req.body as AgentCreationRequest;
      
      if (!command) {
        return res.status(400).json({ error: 'Command is required' });
      }
      
      // Create a temporary agent instance for plan generation
      const agentId = uuidv4();
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
      
      // Log the agent creation attempt
      await logOperation('agent_creation_started', {
        command,
        hasInitialCapabilities: !!initialCapabilities,
        hasPersonalityProfile: !!personalityProfile
      });
      
      // Generate a plan and get suggested name/description
      const { plan, nameAndDescription } = await tempAgent.createWithCommand(command);
      
      // Create the agent in the database with the suggested name and description
      const newAgent = {
        id: agentId,
        name: nameAndDescription.name,
        description: nameAndDescription.description,
        status: 'awaiting_approval',
        capabilities: tempAgent.capabilities,
        settings: tempAgent.settings,
        personalityProfile: tempAgent.personalityProfile
      };
      
      const createdAgent = await db.agents.createAgent(newAgent);
      
      // Save the plan to the database
      const createdPlan = await db.plans.createPlan(plan);
      
      // Log successful creation
      await logOperation('agent_created', {
        agentId,
        planId: createdPlan.id,
        stepCount: createdPlan.steps.length
      });
      
      // Emit socket events
      io.emit('agent:created', createdAgent);
      io.emit('plan:created', {
        agentId,
        planId: createdPlan.id
      });
      
      res.status(201).json({
        agent: createdAgent,
        plan: {
          planId: createdPlan.id,
          status: createdPlan.status,
          description: createdPlan.description,
          steps: createdPlan.steps
        }
      });
    } catch (error) {
      console.error('Error creating agent:', error);
      res.status(500).json({ error: 'Failed to create agent' });
    }
  });

  // Update an agent
  router.put('/:id', async (req: express.Request, res: express.Response) => {
    try {
      const { name, description, status, capabilities, personalityProfile, settings } = req.body;
      const updates: Record<string, any> = {};
      
      if (name !== undefined) updates.name = name;
      if (description !== undefined) updates.description = description;
      if (status !== undefined) updates.status = status;
      if (capabilities !== undefined) updates.capabilities = capabilities;
      if (personalityProfile !== undefined) updates.personalityProfile = personalityProfile;
      if (settings !== undefined) updates.settings = settings;
      
      const updatedAgent = await db.agents.updateAgent(req.params.id, updates);
      
      // Emit socket event
      io.emit('agent:updated', updatedAgent);
      
      res.json(updatedAgent);
    } catch (error) {
      console.error(`Error updating agent ${req.params.id}:`, error);
      res.status(500).json({ error: 'Failed to update agent' });
    }
  });

  // Delete an agent
  router.delete('/:id', async (req: express.Request, res: express.Response) => {
    try {
      const success = await db.agents.deleteAgent(req.params.id);
      
      if (!success) {
        return res.status(404).json({ error: 'Agent not found' });
      }
      
      // Emit socket event
      io.emit('agent:deleted', req.params.id);
      
      res.json({ success: true });
    } catch (error) {
      console.error(`Error deleting agent ${req.params.id}:`, error);
      res.status(500).json({ error: 'Failed to delete agent' });
    }
  });

  // Get current plan for an agent
  router.get('/:id/current-plan', async (req: express.Request, res: express.Response) => {
    try {
      const plan = await db.plans.getCurrentPlanForAgent(req.params.id);
      
      if (!plan) {
        return res.json({ hasPlan: false });
      }
      
      // Fetch follow-up suggestions if they exist
      let followUpSuggestions: any[] = [];
      try {
        // Use a simpler approach that doesn't rely on type checking
        // Get the plan ID to use
        const planId = (plan as any).id;
        
        // First check if the column exists to avoid errors
        const columnCheckSql = `
          SELECT COLUMN_NAME 
          FROM INFORMATION_SCHEMA.COLUMNS 
          WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'plans' AND COLUMN_NAME = 'follow_up_suggestions'
        `;
        const [columnsResult] = await db.pool.query(columnCheckSql, [process.env.DB_NAME || 'times1000']);
        
        // Only query for the column if it exists (the array has at least one element)
        if (Array.isArray(columnsResult) && columnsResult.length > 0) {
          const followUpSql = 'SELECT follow_up_suggestions FROM plans WHERE id = ?';
          const [followUpResult] = await db.pool.query(followUpSql, [planId]);
          
          // If we have a result and it has the property we need
          if (Array.isArray(followUpResult) && 
              followUpResult.length > 0 && 
              followUpResult[0] && 
              'follow_up_suggestions' in followUpResult[0]) {
            
            const suggestions = followUpResult[0].follow_up_suggestions;
            
            // Process the suggestions based on their type
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
      
      res.json(planResponse);
    } catch (error) {
      console.error(`Error fetching plan for agent ${req.params.id}:`, error);
      res.status(500).json({ error: 'Failed to fetch plan' });
    }
  });

  // Send a command to an agent
  router.post('/:id/command', async (req: express.Request, res: express.Response) => {
    try {
      const { command } = req.body;
      const agent = await db.agents.getAgentById(req.params.id);
      
      if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
      }
      
      if (!command) {
        return res.status(400).json({ error: 'Command is required' });
      }
      
      // Log the command receipt
      await logOperation('command_received', {
        agentId: agent.id,
        command
      });
      
      // Create an Agent instance
      const agentInstance = new Agent(agent.id, agent.name, agent.description);
      
      // Set capabilities if they exist
      if (agent.capabilities && Array.isArray(agent.capabilities)) {
        agentInstance.addCapabilities(agent.capabilities);
      }
      
      // Generate a plan with potential name/description update
      const generatedPlan = await agentInstance.receiveCommand(command);
      
      // Save the plan to the database
      const createdPlan = await db.plans.createPlan(generatedPlan);
      
      // Update agent status and possibly name/description if they changed
      const updates: Record<string, any> = { status: 'awaiting_approval' };
      
      // If name or description changed, update them
      if (agentInstance.name !== agent.name) {
        updates.name = agentInstance.name;
      }
      
      if (agentInstance.description !== agent.description) {
        updates.description = agentInstance.description;
      }
      
      await db.agents.updateAgent(agent.id, updates);
      
      // Log plan creation
      await logOperation('plan_created', {
        agentId: agent.id,
        planId: createdPlan.id,
        stepCount: createdPlan.steps.length,
        nameUpdated: 'name' in updates,
        descriptionUpdated: 'description' in updates
      });
      
      // Emit socket events
      io.emit('plan:created', {
        agentId: agent.id,
        planId: createdPlan.id
      });
      
      // If name or description changed, emit update event
      if ('name' in updates || 'description' in updates) {
        io.emit('agent:updated', {
          ...agent,
          ...updates
        });
      }
      
      res.json({
        planId: createdPlan.id,
        agentId: agent.id,
        status: createdPlan.status,
        description: createdPlan.description,
        steps: createdPlan.steps,
        nameUpdated: 'name' in updates ? updates.name : undefined,
        descriptionUpdated: 'description' in updates ? updates.description : undefined
      });
    } catch (error) {
      console.error('Error creating plan:', error);
      res.status(500).json({ error: 'Failed to create plan' });
    }
  });

  return router;
}