import express from 'express';
import db from '../../db';
import { executeAiProcessing } from '../services/plan-service';
import { logOperation } from '../services/logging-service';
import { asyncHandler } from '../middleware/error-middleware';
import { createError } from '../../utils/error-utils';
import { updateAgentStatus, updatePlanStatus } from '../../utils/agent-utils';
import { sendSuccess } from '../../utils/api-utils';
import { eventService } from '../../services/event-service';
import { AGENT_STATUS, PLAN_STATUS } from '../../config/constants';

export default function() {
  const router = express.Router();

  // Approve a plan
  router.post('/:planId/approve', asyncHandler(async (req: express.Request, res: express.Response) => {
    // Extract the agent ID from the plan
    const [planRowsResult] = await db.pool.query(
      'SELECT agent_id FROM plans WHERE id = ?', 
      [req.params.planId]
    );
    
    // Handle result safely
    const planRows = Array.isArray(planRowsResult) ? planRowsResult : [];
    
    if (planRows.length === 0) {
      throw createError('Plan not found', 'PLAN_NOT_FOUND', { planId: req.params.planId }, 404);
    }
    
    // Cast to any to safely access properties
    const planData = planRows[0] as any;
    const agentId = planData.agent_id;
    const agent = await db.agents.getAgentById(agentId);
    
    if (!agent) {
      throw createError('Agent not found', 'AGENT_NOT_FOUND', { agentId }, 404);
    }
    
    // Update plan status to approved
    await updatePlanStatus(req.params.planId, PLAN_STATUS.APPROVED, agentId);
    
    // Update agent status to executing
    await updateAgentStatus(agent.id, AGENT_STATUS.EXECUTING);
    
    // Start the AI processing in the background
    executeAiProcessing(agent.id, req.params.planId);
    
    return sendSuccess(res, {
      planId: req.params.planId,
      status: PLAN_STATUS.APPROVED,
      agentStatus: AGENT_STATUS.EXECUTING
    });
  }));

  // Reject a plan
  router.post('/:planId/reject', asyncHandler(async (req: express.Request, res: express.Response) => {
    // Extract the agent ID from the plan
    const [planRowsResult] = await db.pool.query(
      'SELECT agent_id FROM plans WHERE id = ?', 
      [req.params.planId]
    );
    
    // Handle result safely
    const planRows = Array.isArray(planRowsResult) ? planRowsResult : [];
    
    if (planRows.length === 0) {
      throw createError('Plan not found', 'PLAN_NOT_FOUND', { planId: req.params.planId }, 404);
    }
    
    // Cast to any to safely access properties
    const planData = planRows[0] as any;
    const agentId = planData.agent_id;
    const agent = await db.agents.getAgentById(agentId);
    
    if (!agent) {
      throw createError('Agent not found', 'AGENT_NOT_FOUND', { agentId }, 404);
    }
    
    // Update plan status to rejected
    await updatePlanStatus(req.params.planId, PLAN_STATUS.REJECTED, agentId);
    
    // Update agent status to idle
    await updateAgentStatus(agent.id, AGENT_STATUS.IDLE);
    
    return sendSuccess(res, {
      success: true,
      agentStatus: AGENT_STATUS.IDLE
    });
  }));

  // Get plan details
  router.get('/:planId', asyncHandler(async (req: express.Request, res: express.Response) => {
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
      throw createError('Plan not found', 'PLAN_NOT_FOUND', { planId: req.params.planId }, 404);
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
    
    return sendSuccess(res, {
      ...plan,
      steps: stepRows,
      hasFollowUp: followUpSuggestions.length > 0,
      followUpSuggestions
    });
  }));

  // Request follow-up suggestions
  router.post('/:planId/follow-up', asyncHandler(async (req: express.Request, res: express.Response) => {
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
      throw createError('Plan not found', 'PLAN_NOT_FOUND', { planId: req.params.planId }, 404);
    }
    
    // Cast to any to safely access properties
    const plan = planRows[0] as any;
    const agent = await db.agents.getAgentById(plan.agentId);
    
    if (!agent) {
      throw createError('Agent not found', 'AGENT_NOT_FOUND', { agentId: plan.agentId }, 404);
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
    
    // Emit socket event for follow-up
    eventService.emit('plan:followup', {
      agentId: agent.id,
      planId: plan.id,
      hasFollowUp: followUpSuggestions.length > 0,
      followUpSuggestions
    });
    
    return sendSuccess(res, {
      planId: plan.id,
      hasFollowUp: followUpSuggestions.length > 0,
      followUpSuggestions
    });
  }));

  return router;
}