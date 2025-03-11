export type PlanStatus = 'draft' | 'awaiting_approval' | 'approved' | 'executing' | 'completed' | 'failed' | 'rejected';
export type StepStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

export interface PlanStep {
  id: string;
  description: string;
  status: StepStatus;
  estimatedDuration?: number; // in seconds
  result?: any;
  error?: Error;
  details?: string;
  position?: number; // Add position field
}

export interface Plan {
  id: string;
  agentId: string;
  command: string;
  description: string;
  reasoning: string;
  status: PlanStatus;
  steps: PlanStep[];
  createdAt: Date;
  updatedAt: Date;
  hasFollowUp: boolean;
  followUpSuggestions?: string[];
  estimatedCompletionTime?: number; // in seconds
  
  // Methods for plan management
  addStep(step: Omit<PlanStep, 'id' | 'status'>): void;
  removeStep(stepId: string): void;
  updateStep(stepId: string, updates: Partial<PlanStep>): void;
  reorderSteps(newOrder: string[]): void;
}

export class PlanImpl implements Plan {
  id: string;
  agentId: string;
  command: string;
  description: string;
  reasoning: string;
  status: PlanStatus;
  steps: PlanStep[];
  createdAt: Date;
  updatedAt: Date;
  hasFollowUp: boolean;
  followUpSuggestions?: string[];
  estimatedCompletionTime?: number;
  
  constructor(id: string, agentId: string, command: string, description: string, reasoning: string) {
    this.id = id;
    this.agentId = agentId;
    this.command = command;
    this.description = description;
    this.reasoning = reasoning;
    this.status = 'draft';
    this.steps = [];
    this.createdAt = new Date();
    this.updatedAt = new Date();
    this.hasFollowUp = false;
  }
  
  addStep(step: Omit<PlanStep, 'id' | 'status'>): void {
    // Determine position for the new step
    const position = 'position' in step ? (step as any).position : this.steps.length;
    
    const newStep: PlanStep = {
      id: `${this.id.substring(0, 8)}-s${this.steps.length + 1}`,
      status: 'pending',
      ...step
    };
    
    // Add position if it's not already included
    if (!('position' in newStep)) {
      (newStep as any).position = position;
    }
    
    this.steps.push(newStep);
    this.updatedAt = new Date();
    
    // Recalculate estimated completion time
    this.calculateEstimatedCompletionTime();
  }
  
  removeStep(stepId: string): void {
    const index = this.steps.findIndex(step => step.id === stepId);
    
    if (index !== -1) {
      this.steps.splice(index, 1);
      this.updatedAt = new Date();
      this.calculateEstimatedCompletionTime();
    }
  }
  
  updateStep(stepId: string, updates: Partial<PlanStep>): void {
    const step = this.steps.find(step => step.id === stepId);
    
    if (step) {
      Object.assign(step, updates);
      this.updatedAt = new Date();
      
      if (updates.estimatedDuration !== undefined) {
        this.calculateEstimatedCompletionTime();
      }
    }
  }
  
  reorderSteps(newOrder: string[]): void {
    if (newOrder.length !== this.steps.length) {
      throw new Error('New order must contain all step IDs');
    }
    
    const stepMap = new Map<string, PlanStep>();
    this.steps.forEach(step => stepMap.set(step.id, step));
    
    const newSteps: PlanStep[] = [];
    
    for (const stepId of newOrder) {
      const step = stepMap.get(stepId);
      
      if (!step) {
        throw new Error(`Step with ID ${stepId} not found`);
      }
      
      newSteps.push(step);
    }
    
    this.steps = newSteps;
    this.updatedAt = new Date();
  }
  
  private calculateEstimatedCompletionTime(): void {
    let totalTime = 0;
    
    for (const step of this.steps) {
      if (step.estimatedDuration) {
        totalTime += step.estimatedDuration;
      }
    }
    
    this.estimatedCompletionTime = totalTime > 0 ? totalTime : undefined;
  }
}