import { RowDataPacket, OkPacket, ResultSetHeader } from 'mysql2';
import { PlanStatus, StepStatus } from '../core/Plan';

// Type to make TypeScript recognize the properties of MySQL query results
export type QueryResult = 
  | RowDataPacket[]
  | ResultSetHeader[]
  | OkPacket
  | ResultSetHeader;

// Enhanced RowDataPacket with follow-up suggestions
export interface PlanRowData extends RowDataPacket {
  id: string;
  agentId: string;
  command: string;
  description: string;
  reasoning: string;
  status: string;
  createdAt: Date;
  updatedAt: Date;
  follow_up_suggestions?: string | any[];
}

// Define interfaces for plan and step structures
export interface Plan {
  id: string;
  agentId: string;
  command: string;
  description: string;
  reasoning: string;
  status: PlanStatus;
  steps: PlanStep[];
  createdAt?: Date;
  updatedAt?: Date;
  hasFollowUp?: boolean;
  followUpSuggestions?: string[];
  // Include methods from core Plan class
  addStep?: (step: PlanStep) => void;
  removeStep?: (stepId: string) => void;
  updateStep?: (stepId: string, updates: Partial<PlanStep>) => void;
  getStepById?: (stepId: string) => PlanStep | undefined;
  reorderSteps?: (stepIds: string[]) => void;
}

export interface PlanStep {
  id: string;
  description: string;
  status: StepStatus;
  result?: string;
  estimatedDuration?: number;
  details?: string;
  position: number;
}