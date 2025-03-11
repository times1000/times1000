import { Server } from 'socket.io';
import { EVENTS } from '../config/constants';

/**
 * Central service for emitting events
 * Decouples event emitting from direct Socket.io usage
 */
export class EventService {
  private static instance: EventService;
  private io: Server | null = null;
  
  private constructor() {}
  
  /**
   * Get the singleton instance
   */
  public static getInstance(): EventService {
    if (!EventService.instance) {
      EventService.instance = new EventService();
    }
    return EventService.instance;
  }
  
  /**
   * Initialize with Socket.io server
   */
  public initialize(io: Server): void {
    this.io = io;
  }
  
  /**
   * Emit an event
   */
  public emit(eventName: string, data: any): void {
    if (!this.io) {
      console.warn(`Attempted to emit event ${eventName} but Socket.io is not initialized`);
      return;
    }
    
    this.io.emit(eventName, data);
  }
  
  /**
   * Agent status update event
   */
  public emitAgentStatusUpdate(agentId: string, status: string): void {
    this.emit(EVENTS.AGENT.STATUS_CHANGED, { agentId, status });
    this.emit(EVENTS.AGENT.UPDATED, { id: agentId, status });
  }
  
  /**
   * Agent updated event
   */
  public emitAgentUpdated(agent: any): void {
    this.emit(EVENTS.AGENT.UPDATED, agent);
  }
  
  /**
   * Plan created event
   */
  public emitPlanCreated(agentId: string, planId: string): void {
    this.emit(EVENTS.PLAN.CREATED, { agentId, planId });
  }
  
  /**
   * Plan status update events
   */
  public emitPlanApproved(agentId: string, planId: string): void {
    this.emit(EVENTS.PLAN.APPROVED, { agentId, planId });
  }
  
  public emitPlanRejected(agentId: string, planId: string): void {
    this.emit(EVENTS.PLAN.REJECTED, { agentId, planId });
  }
  
  /**
   * Step status update events
   */
  public emitStepStarted(agentId: string, planId: string, stepId: string): void {
    this.emit(EVENTS.STEP.STARTED, { agentId, planId, stepId });
  }
  
  public emitStepCompleted(agentId: string, planId: string, stepId: string, result: any): void {
    this.emit(EVENTS.STEP.COMPLETED, { agentId, planId, stepId, result });
  }
}

// Export a singleton instance
export const eventService = EventService.getInstance();