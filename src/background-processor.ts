import db from './db';
import { logOperation } from './api/services/logging-service';
import { executeAiProcessing } from './api/services/plan-service';
import { Server } from 'socket.io';
import { AgentStatus, AgentData } from './types/agent';
import { RowDataPacket } from 'mysql2';

/**
 * Background processor that checks for agents with plans awaiting approval
 * and agents with approved plans that need to be executed
 */
export class BackgroundProcessor {
  private io: Server;
  private running: boolean = false;
  private pollInterval: number = 5000; // 5 seconds
  private intervalId: NodeJS.Timeout | null = null;

  constructor(io: Server) {
    this.io = io;
    
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

    // Verify LLM API keys are set
    const hasOpenAIKey = !!process.env.OPENAI_API_KEY;
    const hasAnthropicKey = !!process.env.ANTHROPIC_API_KEY;
    
    if (!hasOpenAIKey && !hasAnthropicKey) {
      console.warn('WARNING: Starting background processor without any LLM API keys. LLM tasks will fail.');
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
      hasOpenAIKey,
      hasAnthropicKey,
      defaultProvider: process.env.DEFAULT_LLM_PROVIDER || 'openai'
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
      // Use direct query as a workaround for type issues
      const [rows] = await db.pool.query(
        'SELECT * FROM agents WHERE status = ?', 
        [AgentStatus.EXECUTING]
      );
      
      // Convert result to an array of agents
      const agents = rows as RowDataPacket[];
      
      for (const agent of agents) {
        // Get the latest plan for this agent
        const plan = await db.plans.getCurrentPlanForAgent(agent.id);
        if (!plan) continue;
        
        // Converting to any for safety since RowDataPacket doesn't have the expected fields
        const planData = plan as any;
        
        // If plan exists and is approved but not executing yet
        if (planData.status === 'approved') {
          console.log(`Processing approved plan ${planData.id} for agent ${agent.id}`);
          
          // Log the operation
          await logOperation('background_processing_plan', {
            agentId: agent.id,
            planId: planData.id,
            agentName: agent.name
          });
          
          // Execute the plan in background
          executeAiProcessing(this.io, agent.id, planData.id);
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
      // Use direct query as a workaround for type issues
      const [rows] = await db.pool.query(
        'SELECT * FROM agents WHERE status = ?',
        [AgentStatus.AWAITING_APPROVAL]
      );
      
      // Convert result to an array of agents
      const agents = rows as RowDataPacket[];
      
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
export function startBackgroundProcessor(io: Server): BackgroundProcessor {
  const processor = new BackgroundProcessor(io);
  processor.start();
  return processor;
}