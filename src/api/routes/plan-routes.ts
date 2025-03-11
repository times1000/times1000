import express from 'express';
import db from '../../db';
import { executeAiProcessing } from '../services/plan-service';
import { logOperation } from '../services/logging-service';
import { Server } from 'socket.io';

export default function(io: Server) {
  const router = express.Router();

  // Approve a plan
  router.post('/:planId/approve', async (req: express.Request, res: express.Response) => {
    try {
      // Extract the agent ID from the plan
      const [planRowsResult] = await db.pool.query(
        'SELECT agent_id FROM plans WHERE id = ?', 
        [req.params.planId]
      );
      
      // Handle result safely
      const planRows = Array.isArray(planRowsResult) ? planRowsResult : [];
      
      if (planRows.length === 0) {
        return res.status(404).json({ error: 'Plan not found' });
      }
      
      // Cast to any to safely access properties
      const planData = planRows[0] as any;
      const agentId = planData.agent_id;
      const agent = await db.agents.getAgentById(agentId);
      
      if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
      }
      
      // Update plan status to approved
      await db.plans.updatePlanStatus(req.params.planId, 'approved');
      
      // Update agent status to executing
      await db.agents.updateAgent(agent.id, { status: 'executing' });
      
      // Log the approval
      await logOperation('plan_approved', {
        agentId: agent.id,
        planId: req.params.planId,
        agentName: agent.name
      });
      
      // Emit socket event
      io.emit('plan:approved', {
        agentId: agent.id,
        planId: req.params.planId
      });
      
      // Start the AI processing in the background
      executeAiProcessing(io, agent.id, req.params.planId);
      
      res.json({
        planId: req.params.planId,
        status: 'approved',
        agentStatus: 'executing'
      });
    } catch (error) {
      console.error('Error approving plan:', error);
      res.status(500).json({ error: 'Failed to approve plan' });
    }
  });

  // Reject a plan
  router.post('/:planId/reject', async (req: express.Request, res: express.Response) => {
    try {
      // Extract the agent ID from the plan
      const [planRowsResult] = await db.pool.query(
        'SELECT agent_id FROM plans WHERE id = ?', 
        [req.params.planId]
      );
      
      // Handle result safely
      const planRows = Array.isArray(planRowsResult) ? planRowsResult : [];
      
      if (planRows.length === 0) {
        return res.status(404).json({ error: 'Plan not found' });
      }
      
      // Cast to any to safely access properties
      const planData = planRows[0] as any;
      const agentId = planData.agent_id;
      const agent = await db.agents.getAgentById(agentId);
      
      if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
      }
      
      // Update plan status to rejected
      await db.plans.updatePlanStatus(req.params.planId, 'rejected');
      
      // Update agent status to idle
      await db.agents.updateAgent(agent.id, { status: 'idle' });
      
      // Log the rejection
      await logOperation('plan_rejected', {
        agentId: agent.id,
        planId: req.params.planId,
        agentName: agent.name
      });
      
      // Emit socket event
      io.emit('plan:rejected', {
        agentId: agent.id,
        planId: req.params.planId
      });
      
      res.json({
        success: true,
        agentStatus: 'idle'
      });
    } catch (error) {
      console.error('Error rejecting plan:', error);
      res.status(500).json({ error: 'Failed to reject plan' });
    }
  });

  // Get plan details
  router.get('/:planId', async (req: express.Request, res: express.Response) => {
    try {
      // First fetch the plan
      const [planRowsResult] = await db.pool.query(`
        SELECT 
          id, agent_id AS agentId, command, description, 
          reasoning, status, created_at AS createdAt, 
          updated_at AS updatedAt, follow_up_suggestions
        FROM plans 
        WHERE id = ?
      `, [req.params.planId]);
      
      // Handle result safely
      const planRows = Array.isArray(planRowsResult) ? planRowsResult : [];
      
      if (planRows.length === 0) {
        return res.status(404).json({ error: 'Plan not found' });
      }
      
      // Cast to any to safely access properties
      const plan = planRows[0] as any;
      
      // Get steps for this plan
      const [stepRows] = await db.pool.query(`
        SELECT 
          id, description, status, result, 
          estimated_duration AS estimatedDuration, 
          position
        FROM plan_steps
        WHERE plan_id = ?
        ORDER BY position
      `, [plan.id]);
      
      // Parse follow-up suggestions if they exist
      let followUpSuggestions: any[] = [];
      if (plan && 'follow_up_suggestions' in plan && plan.follow_up_suggestions) {
        followUpSuggestions = typeof plan.follow_up_suggestions === 'string'
          ? JSON.parse(plan.follow_up_suggestions)
          : plan.follow_up_suggestions;
      }
      
      res.json({
        ...plan,
        steps: stepRows,
        hasFollowUp: followUpSuggestions.length > 0,
        followUpSuggestions
      });
    } catch (error) {
      console.error(`Error fetching plan ${req.params.planId}:`, error);
      res.status(500).json({ error: 'Failed to fetch plan' });
    }
  });

  // Request follow-up suggestions
  router.post('/:planId/follow-up', async (req: express.Request, res: express.Response) => {
    try {
      // Get the plan and its associated agent
      const [planRowsResult] = await db.pool.query(`
        SELECT 
          id, agent_id AS agentId, command, description, 
          reasoning, status
        FROM plans 
        WHERE id = ?
      `, [req.params.planId]);
      
      // Handle result safely
      const planRows = Array.isArray(planRowsResult) ? planRowsResult : [];
      
      if (planRows.length === 0) {
        return res.status(404).json({ error: 'Plan not found' });
      }
      
      // Cast to any to safely access properties
      const plan = planRows[0] as any;
      const agent = await db.agents.getAgentById(plan.agentId);
      
      if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
      }
      
      // Import generateFollowUpSuggestions function
      // This is a dynamic import to avoid circular dependency issues
      const planService = await import('../services/plan-service');
      const followUpSuggestions = await planService.generateFollowUpSuggestions(plan, agent);
      
      // Store follow-up suggestions in the database
      try {
        await db.pool.query(`
          UPDATE plans 
          SET follow_up_suggestions = ? 
          WHERE id = ?
        `, [JSON.stringify(followUpSuggestions), plan.id]);
      } catch (error) {
        console.log('Could not store follow-up suggestions:', error instanceof Error ? error.message : 'Unknown error');
      }
      
      // Log follow-up generation
      await logOperation('follow_up_generation', {
        agentId: agent.id,
        planId: plan.id,
        suggestionCount: followUpSuggestions.length
      });
      
      // Emit socket event
      io.emit('plan:followup', {
        agentId: agent.id,
        planId: plan.id,
        hasFollowUp: followUpSuggestions.length > 0,
        followUpSuggestions
      });
      
      res.json({
        planId: plan.id,
        hasFollowUp: followUpSuggestions.length > 0,
        followUpSuggestions
      });
    } catch (error) {
      console.error(`Error generating follow-up suggestions for plan ${req.params.planId}:`, error);
      res.status(500).json({ error: 'Failed to generate follow-up suggestions' });
    }
  });

  return router;
}