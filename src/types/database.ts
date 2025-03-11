import { RowDataPacket } from 'mysql2/promise';

// Database model for Agent
export interface AgentRow extends RowDataPacket {
  id: string;
  name: string;
  type: string;
  description: string;
  status: string;
  created_at: Date;
  last_active: Date;
  capabilities: string;
  personality_profile?: string;
}

// Database model for Plan
export interface PlanRow extends RowDataPacket {
  id: string;
  agent_id: string;
  title: string;
  description: string;
  status: string;
  created_at: Date;
  updated_at: Date;
  has_follow_up: boolean;
}

// Database model for Plan Step
export interface PlanStepRow extends RowDataPacket {
  id: string;
  plan_id: string;
  description: string;
  order_index: number;
  status: string;
  details?: string;
  result?: string;
  created_at: Date;
  updated_at: Date;
}

// Database model for Log Entry
export interface LogEntryRow extends RowDataPacket {
  id: string;
  agent_id?: string;
  level: string;
  message: string;
  timestamp: Date;
  context?: string;
}