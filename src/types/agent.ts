export enum AgentStatus {
  IDLE = 'idle',
  PLANNING = 'planning',
  PLAN_PENDING = 'plan_pending',
  AWAITING_APPROVAL = 'awaiting_approval',
  EXECUTING = 'executing',
  ERROR = 'error'
}

export interface AgentConfig {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  settings: Record<string, any>;
}

export interface AgentData {
  id: string;
  name: string;
  type?: string;
  description: string;
  status: AgentStatus;
  capabilities: string[];
  personalityProfile?: string;
  settings?: Record<string, any>;
  createdAt: Date;
  lastActive: Date;
}

export interface AgentStats {
  plansCreated: number;
  plansExecuted: number;
  plansRejected: number;
  executionTime: number;
  successRate: number;
}

export interface AgentCreationRequest {
  command: string;
  initialCapabilities?: string[];
  personalityProfile?: string;
  settings?: Record<string, any>;
}

export interface PlanGenerationQueueItem {
  agentId: string;
  command: string;
  isInitialPlan: boolean;
  requestId: string;
}