import EventEmitter from 'events';
import { Plan, PlanStep } from './Plan';
import { generatePlan } from './PlanGenerator';
import { AgentStatus } from '../types/agent';
import { DEFAULT_MAX_LISTENERS, AGENT_STATUS, STEP_STATUS, PLAN_STATUS } from '../config/constants';
import { logError } from '../utils/error-utils';

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
    // Set maximum listeners to avoid memory leaks with many listeners
    this.setMaxListeners(DEFAULT_MAX_LISTENERS);
    
    this.id = id;
    this.name = name;
    this.description = description;
    this.status = AgentStatus.IDLE;
    this.currentPlan = null;
    this.personalityProfile = '';
    this.capabilities = [];
    this.settings = {};
  }
  
  /**
   * Update the agent's status and emit events
   */
  private updateStatus(status: AgentStatus): void {
    this.status = status;
    this.emit('statusChange', this.status);
  }
  
  /**
   * Handle plan metadata updates
   */
  private updateMetadata(name?: string, description?: string): void {
    let updated = false;
    
    if (name && name !== this.name) {
      this.name = name;
      updated = true;
    }
    
    if (description && description !== this.description) {
      this.description = description;
      updated = true;
    }
    
    if (updated) {
      this.emit('metadataUpdated', { 
        name: this.name, 
        description: this.description 
      });
    }
  }
  
  /**
   * Validate the current plan exists
   */
  private validatePlanExists(): void {
    if (!this.currentPlan) {
      throw new Error('No plan available');
    }
  }
  
  /**
   * Validate the agent status matches expected status
   */
  private validateStatus(expectedStatus: AgentStatus | AgentStatus[]): void {
    const statusArray = Array.isArray(expectedStatus) ? expectedStatus : [expectedStatus];
    
    if (!statusArray.includes(this.status)) {
      throw new Error(`Agent status is ${this.status}, expected one of: ${statusArray.join(', ')}`);
    }
  }

  async createWithCommand(command: string): Promise<{ plan: Plan, nameAndDescription: { name: string, description: string } }> {
    // Update status to planning
    this.updateStatus(AgentStatus.PLANNING);
    
    try {
      // Generate a plan based on the command with real AI
      const { plan, agentNameAndDescription } = await generatePlan(this, command, true);
      this.currentPlan = plan;
      
      // Update agent name and description based on plan
      if (agentNameAndDescription) {
        this.updateMetadata(agentNameAndDescription.name, agentNameAndDescription.description);
      }
      
      // Update status to awaiting approval
      this.updateStatus(AgentStatus.AWAITING_APPROVAL);
      this.emit('planCreated', plan);
      
      return { 
        plan, 
        nameAndDescription: { 
          name: this.name, 
          description: this.description 
        } 
      };
    } catch (error) {
      // Log and handle error
      logError(error, `Agent.createWithCommand(${this.id})`);
      this.updateStatus(AgentStatus.ERROR);
      this.emit('error', error);
      throw error;
    }
  }

  async receiveCommand(command: string): Promise<Plan> {
    // Update status to planning
    this.updateStatus(AgentStatus.PLANNING);
    
    try {
      // Generate a plan based on the command with real AI
      const { plan, agentNameAndDescription } = await generatePlan(this, command);
      this.currentPlan = plan;
      
      // Optionally update agent name and description based on new plan
      if (agentNameAndDescription) {
        this.updateMetadata(agentNameAndDescription.name, agentNameAndDescription.description);
      }
      
      // Update status to awaiting approval
      this.updateStatus(AgentStatus.AWAITING_APPROVAL);
      this.emit('planCreated', plan);
      
      return plan;
    } catch (error) {
      // Log and handle error
      logError(error, `Agent.receiveCommand(${this.id})`);
      this.updateStatus(AgentStatus.ERROR);
      this.emit('error', error);
      throw error;
    }
  }

  async executePlan(): Promise<void> {
    // Validate the current plan exists and status is correct
    this.validatePlanExists();
    this.validateStatus(AgentStatus.AWAITING_APPROVAL);
    
    // Update status to executing
    this.updateStatus(AgentStatus.EXECUTING);
    
    try {
      // Execute each step in the plan
      for (const step of this.currentPlan!.steps) {
        // Update step status
        step.status = STEP_STATUS.IN_PROGRESS;
        this.emit('stepStatusChange', step);
        
        // Execute the step
        const result = await this.executeStep(step);
        step.result = result;
        
        // Update step status to completed
        step.status = STEP_STATUS.COMPLETED;
        this.emit('stepStatusChange', step);
      }
      
      // Plan completed successfully
      this.currentPlan!.status = PLAN_STATUS.COMPLETED;
      this.updateStatus(AgentStatus.IDLE);
      this.emit('planCompleted', this.currentPlan);
      
      // Generate follow-up plan if applicable
      if (this.currentPlan!.hasFollowUp) {
        this.receiveCommand('Based on the completed plan, what follow-up actions are recommended?');
      }
    } catch (error) {
      // Log and handle error
      logError(error, `Agent.executePlan(${this.id})`);
      this.updateStatus(AgentStatus.ERROR);
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
    // Validate the current plan exists and status is correct
    this.validatePlanExists();
    this.validateStatus(AgentStatus.AWAITING_APPROVAL);
    
    // Update plan status
    this.currentPlan!.status = PLAN_STATUS.APPROVED;
    this.emit('planApproved', this.currentPlan);
  }

  rejectPlan(): void {
    // Validate the current plan exists and status is correct
    this.validatePlanExists();
    this.validateStatus(AgentStatus.AWAITING_APPROVAL);
    
    // Update plan and agent status
    this.currentPlan!.status = PLAN_STATUS.REJECTED;
    this.updateStatus(AgentStatus.IDLE);
    this.currentPlan = null;
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