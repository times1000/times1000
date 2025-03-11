import EventEmitter from 'events';
import { Plan, PlanStep } from './Plan';
import { generatePlan } from './PlanGenerator';
import { AgentStatus } from '../types/agent';

/**
 * Unified Agent class that replaces all specialized agent types.
 * This is a concrete class that can be instantiated directly with configurable capabilities.
 */
export class Agent extends EventEmitter {
  id: string;
  name: string;
  description: string;
  status: AgentStatus;
  currentPlan: Plan | null;
  personalityProfile: string;
  capabilities: string[];
  settings: Record<string, any>;
  
  constructor(id: string, name: string = 'Unnamed Agent', description: string = 'Agent awaiting configuration') {
    super();
    this.id = id;
    this.name = name;
    this.description = description;
    this.status = AgentStatus.IDLE;
    this.currentPlan = null;
    this.personalityProfile = '';
    this.capabilities = [];
    this.settings = {};
  }

  async createWithCommand(command: string): Promise<{ plan: Plan, nameAndDescription: { name: string, description: string } }> {
    this.status = AgentStatus.PLANNING;
    this.emit('statusChange', this.status);
    
    try {
      // Generate a plan based on the command with real AI
      const { plan, agentNameAndDescription } = await generatePlan(this, command, true);
      this.currentPlan = plan;
      
      // Update agent name and description based on plan
      if (agentNameAndDescription) {
        this.name = agentNameAndDescription.name;
        this.description = agentNameAndDescription.description;
        this.emit('metadataUpdated', { name: this.name, description: this.description });
      }
      
      this.status = AgentStatus.AWAITING_APPROVAL;
      this.emit('statusChange', this.status);
      this.emit('planCreated', plan);
      
      return { 
        plan, 
        nameAndDescription: { 
          name: this.name, 
          description: this.description 
        } 
      };
    } catch (error: any) {
      this.status = AgentStatus.ERROR;
      this.emit('statusChange', this.status);
      this.emit('error', error);
      throw error;
    }
  }

  async receiveCommand(command: string): Promise<Plan> {
    this.status = AgentStatus.PLANNING;
    this.emit('statusChange', this.status);
    
    try {
      // Generate a plan based on the command with real AI
      const { plan, agentNameAndDescription } = await generatePlan(this, command);
      this.currentPlan = plan;
      
      // Optionally update agent name and description based on new plan
      if (agentNameAndDescription) {
        this.name = agentNameAndDescription.name;
        this.description = agentNameAndDescription.description;
        this.emit('metadataUpdated', { name: this.name, description: this.description });
      }
      
      this.status = AgentStatus.AWAITING_APPROVAL;
      this.emit('statusChange', this.status);
      this.emit('planCreated', plan);
      
      return plan;
    } catch (error: any) {
      this.status = AgentStatus.ERROR;
      this.emit('statusChange', this.status);
      this.emit('error', error);
      throw error;
    }
  }

  async executePlan(): Promise<void> {
    if (!this.currentPlan) {
      throw new Error('No plan to execute');
    }
    
    if (this.status !== AgentStatus.AWAITING_APPROVAL) {
      throw new Error('Plan has not been approved');
    }
    
    this.status = AgentStatus.EXECUTING;
    this.emit('statusChange', this.status);
    
    try {
      for (const step of this.currentPlan.steps) {
        step.status = 'in_progress';
        this.emit('stepStatusChange', step);
        
        // Execute the step
        const result = await this.executeStep(step);
        step.result = result;
        
        step.status = 'completed';
        this.emit('stepStatusChange', step);
      }
      
      // Plan completed successfully
      this.currentPlan.status = 'completed';
      this.status = AgentStatus.IDLE;
      this.emit('statusChange', this.status);
      this.emit('planCompleted', this.currentPlan);
      
      // Generate follow-up plan if applicable
      if (this.currentPlan.hasFollowUp) {
        this.receiveCommand('Based on the completed plan, what follow-up actions are recommended?');
      }
    } catch (error: any) {
      this.status = AgentStatus.ERROR;
      this.emit('statusChange', this.status);
      this.emit('error', error);
      throw error;
    }
  }

  async executeStep(step: PlanStep): Promise<string> {
    // Default implementation for executing a step
    // In the unified architecture, this is a configurable method rather than requiring subclassing
    return `Step "${step.description}" executed by agent ${this.name}.\nThis step would perform: ${step.details || step.description}`;
  }

  approvePlan(): void {
    if (!this.currentPlan) {
      throw new Error('No plan to approve');
    }
    
    if (this.status !== AgentStatus.AWAITING_APPROVAL) {
      throw new Error('Agent is not awaiting approval');
    }
    
    this.currentPlan.status = 'approved';
    this.emit('planApproved', this.currentPlan);
  }

  rejectPlan(): void {
    if (!this.currentPlan) {
      throw new Error('No plan to reject');
    }
    
    if (this.status !== AgentStatus.AWAITING_APPROVAL) {
      throw new Error('Agent is not awaiting approval');
    }
    
    this.currentPlan.status = 'rejected';
    this.status = AgentStatus.IDLE;
    this.currentPlan = null;
    this.emit('statusChange', this.status);
    this.emit('planRejected');
  }

  setPersonalityProfile(profile: string): void {
    this.personalityProfile = profile;
    this.emit('personalityUpdated', profile);
  }

  addCapability(capability: string): void {
    if (!this.capabilities.includes(capability)) {
      this.capabilities.push(capability);
      this.emit('capabilitiesUpdated', this.capabilities);
    }
  }

  addCapabilities(capabilities: string[]): void {
    const newCapabilities = capabilities.filter(cap => !this.capabilities.includes(cap));
    if (newCapabilities.length > 0) {
      this.capabilities = [...this.capabilities, ...newCapabilities];
      this.emit('capabilitiesUpdated', this.capabilities);
    }
  }

  setSetting(key: string, value: any): void {
    this.settings[key] = value;
    this.emit('settingsUpdated', this.settings);
  }

  getSetting(key: string): any {
    return this.settings[key];
  }
}