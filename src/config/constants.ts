/**
 * Application constants
 */

export const DEFAULT_PAGE_SIZE = 20;
export const DEFAULT_MAX_LISTENERS = 20;
export const BACKGROUND_POLL_INTERVAL_MS = 5000;

/**
 * Agent status constants
 */
export const AGENT_STATUS = {
  IDLE: 'idle',
  PLANNING: 'planning',
  PLAN_PENDING: 'plan_pending',
  AWAITING_APPROVAL: 'awaiting_approval',
  EXECUTING: 'executing',
  COMPLETED: 'completed',
  FAILED: 'failed',
  ERROR: 'error'
};

/**
 * Plan status constants
 */
export const PLAN_STATUS = {
  DRAFT: 'draft',
  PENDING: 'pending',
  APPROVED: 'approved',
  REJECTED: 'rejected',
  EXECUTING: 'executing',
  COMPLETED: 'completed',
  FAILED: 'failed'
};

/**
 * Step status constants
 */
export const STEP_STATUS = {
  PENDING: 'pending',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
  FAILED: 'failed'
};

/**
 * API response format constants
 */
export const API_RESPONSE = {
  SUCCESS: { success: true },
  CREATED: { success: true, status: 'created' },
  UPDATED: { success: true, status: 'updated' },
  DELETED: { success: true, status: 'deleted' }
};

/**
 * Database configuration
 */
export const DB_CONFIG = {
  CONNECTION_RETRY_ATTEMPTS: 10,
  CONNECTION_RETRY_DELAY_MS: 5000,
  CONNECTION_TIMEOUT_MS: 60000,
};

/**
 * Event types
 */
export const EVENTS = {
  AGENT: {
    CREATED: 'agent:created',
    UPDATED: 'agent:updated',
    DELETED: 'agent:deleted',
    STATUS_CHANGED: 'agent:status-changed',
  },
  PLAN: {
    CREATED: 'plan:created',
    APPROVED: 'plan:approved',
    REJECTED: 'plan:rejected',
    COMPLETED: 'plan:completed',
    FAILED: 'plan:failed',
    FOLLOWUP: 'plan:followup',
  },
  STEP: {
    STARTED: 'step:started',
    COMPLETED: 'step:completed',
    FAILED: 'step:failed',
  }
};