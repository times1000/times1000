import db from '../db';
import { logOperation } from '../api/services/logging-service';
import { eventService } from '../services/event-service';
import { AGENT_STATUS, PLAN_STATUS } from '../config/constants';
import { createError } from './error-utils';

/**
 * Update agent status with standardized event emission and logging
 */
export async function updateAgentStatus(
  agentId: string, 
  status: string, 
  details?: Record<string, any>
): Promise<void> {
  try {
    // Update database
    await db.agents.updateAgent(agentId, { status, ...details });
    
    // Emit event
    eventService.emitAgentStatusUpdate(agentId, status);
    
    // Log operation
    await logOperation('agent_status_updated', {
      agentId,
      status,
      details: details || {}
    });
  } catch (error) {
    throw createError(
      `Failed to update agent status to ${status}`,
      'UPDATE_AGENT_STATUS_FAILED',
      { agentId, status, details },
      500
    );
  }
}

/**
 * Validate agent status against expected status
 */
export async function validateAgentStatus(
  agentId: string, 
  expectedStatus: string | string[]
): Promise<any> {
  // Get agent
  const agent = await db.agents.getAgentById(agentId);
  
  if (!agent) {
    throw createError(
      'Agent not found',
      'AGENT_NOT_FOUND',
      { agentId },
      404
    );
  }
  
  // Check if status matches expected
  const statusArray = Array.isArray(expectedStatus) ? expectedStatus : [expectedStatus];
  
  if (!statusArray.includes(agent.status)) {
    throw createError(
      `Agent status is ${agent.status}, expected one of: ${statusArray.join(', ')}`,
      'INVALID_AGENT_STATUS',
      { agentId, currentStatus: agent.status, expectedStatus },
      400
    );
  }
  
  return agent;
}

/**
 * Update plan status with standardized event emission and logging
 */
export async function updatePlanStatus(
  planId: string,
  status: string,
  agentId?: string
): Promise<void> {
  try {
    // Update database
    await db.plans.updatePlanStatus(planId, status);
    
    // Get agent ID if not provided
    if (!agentId) {
      const [planRowsResult] = await db.pool.query(
        'SELECT agent_id FROM plans WHERE id = ?', 
        [planId]
      );
      
      // Handle result safely
      const planRows = Array.isArray(planRowsResult) ? planRowsResult : [];
      
      if (planRows.length > 0) {
        // Cast to any to safely access properties
        const planData = planRows[0] as any;
        agentId = planData.agent_id;
      }
    }
    
    // Only emit events if we have an agent ID
    if (agentId) {
      // Emit appropriate event based on status
      switch (status) {
        case PLAN_STATUS.APPROVED:
          eventService.emitPlanApproved(agentId, planId);
          break;
        case PLAN_STATUS.REJECTED:
          eventService.emitPlanRejected(agentId, planId);
          break;
      }
      
      // Log operation
      await logOperation(`plan_${status}`, {
        agentId,
        planId
      });
    }
  } catch (error) {
    throw createError(
      `Failed to update plan status to ${status}`,
      'UPDATE_PLAN_STATUS_FAILED',
      { planId, status, agentId },
      500
    );
  }
}