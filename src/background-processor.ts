import db from './db';
import { logOperation } from './api/services/logging-service';
import { executeAiProcessing } from './api/services/plan-service';
import { Server } from 'socket.io';
import OpenAI from 'openai';
import { AgentStatus } from './types/agent';

/**
 * Background processor that checks for agents with plans awaiting approval
 * and agents with approved plans that need to be executed
 */
export class BackgroundProcessor {
  private io: Server;
  private openai: OpenAI;
  private running: boolean = false;
  private pollInterval: number = 5000; // 5 seconds
  private intervalId: NodeJS.Timeout | null = null;

  constructor(io: Server, openai: OpenAI) {
    this.io = io;
    this.openai = openai;
    
    // Add error handler for Socket.IO
    this.io.on('error', (error) => {
      console.error('Socket.IO error in background processor:', error);
      logOperation('background_processor_socket_error', {
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    });
  }

  /**
   * Start the background processor
   */
  public start(): void {
    if (this.running) {
      console.log('Background processor is already running');
      return;
    }

    // Verify OpenAI API key is set
    if (!process.env.OPENAI_API_KEY) {
      console.warn('WARNING: Starting background processor without OpenAI API key. LLM tasks will fail.');
    }

    console.log('Starting background processor');
    this.running = true;
    
    // Start processing immediately
    this.processPendingTasks();
    
    // Then set up interval for regular polling
    this.intervalId = setInterval(() => {
      this.processPendingTasks();
    }, this.pollInterval);

    logOperation('background_processor_started', {
      pollInterval: this.pollInterval,
      hasApiKey: !!process.env.OPENAI_API_KEY
    });
  }

  /**
   * Stop the background processor
   */
  public stop(): void {
    if (!this.running) {
      console.log('Background processor is not running');
      return;
    }

    console.log('Stopping background processor');
    this.running = false;
    
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }

    logOperation('background_processor_stopped', {});
  }

  /**
   * Process any pending tasks
   */
  private async processPendingTasks(): Promise<void> {
    try {
      // Process agents with plans that have been approved but not executed
      await this.processApprovedPlans();

      // Process agents with awaiting_approval status
      await this.processAwaitingApprovalAgents();
    } catch (error) {
      console.error('Error in background processor:', error);
      logOperation('background_processor_error', {
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  }

  /**
   * Process agents with plans that have been approved but not executed
   */
  private async processApprovedPlans(): Promise<void> {
    try {
      // Find agents with executing status
      const agents = await db.agents.getAgentsByStatus(AgentStatus.EXECUTING);
      
      for (const agent of agents) {
        // Get the latest plan for this agent
        const plan = await db.plans.getCurrentPlanForAgent(agent.id);
        if (!plan) continue;
        
        // If plan exists and is approved but not executing yet
        if (plan.status === 'approved') {
          console.log(`Processing approved plan ${plan.id} for agent ${agent.id}`);
          
          // Log the operation
          await logOperation('background_processing_plan', {
            agentId: agent.id,
            planId: plan.id,
            agentName: agent.name
          });
          
          // Execute the plan in background
          executeAiProcessing(this.openai, this.io, agent.id, plan.id);
        }
      }
    } catch (error) {
      console.error('Error processing approved plans:', error);
      throw error;
    }
  }

  /**
   * Process agents with awaiting_approval status to notify users
   */
  private async processAwaitingApprovalAgents(): Promise<void> {
    try {
      // Find agents with awaiting_approval status
      const agents = await db.agents.getAgentsByStatus(AgentStatus.AWAITING_APPROVAL);
      
      if (agents.length > 0) {
        // Emit a socket event with all agents awaiting approval
        const awaitingApprovalData = await Promise.all(
          agents.map(async (agent) => {
            const plan = await db.plans.getCurrentPlanForAgent(agent.id);
            return {
              agent,
              plan: plan || null
            };
          })
        );
        
        // Filter out agents without plans
        const validData = awaitingApprovalData.filter(item => item.plan !== null);
        
        // Emit socket event if there are any valid items
        if (validData.length > 0) {
          this.io.emit('agents:awaiting_approval', validData);
        }
      }
    } catch (error) {
      console.error('Error processing awaiting approval agents:', error);
      throw error;
    }
  }
}

/**
 * Create and start the background processor
 */
export function startBackgroundProcessor(io: Server, openai: OpenAI): BackgroundProcessor {
  const processor = new BackgroundProcessor(io, openai);
  processor.start();
  return processor;
}