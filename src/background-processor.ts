import db from './db';
import { logOperation, logSystemOperation } from './api/services/logging-service';
import { executeAiProcessing, generatePlan } from './api/services/plan-service';
import { Server } from 'socket.io';
import { AgentStatus, PlanGenerationQueueItem } from './types/agent';
import { RowDataPacket } from 'mysql2';
import { Plan } from './types/db';
import { v4 as uuidv4 } from 'uuid';

/**
 * Background processor that checks for agents with plans awaiting approval
 * and agents with approved plans that need to be executed
 */
export class BackgroundProcessor {
  private io: Server;
  private running: boolean = false;
  private pollInterval: number = 5000; // 5 seconds
  private intervalId: NodeJS.Timeout | null = null;
  private planGenerationQueue: PlanGenerationQueueItem[] = [];

  constructor(io: Server) {
    this.io = io;
    
    // Add error handler for Socket.IO
    this.io.on('error', (error) => {
      console.error('Socket.IO error in background processor:', error);
      logSystemOperation('socket_error', {
        source: 'background_processor',
        message: 'Socket.IO error in background processor',
        details: JSON.stringify({error: error instanceof Error ? error.message : 'Unknown error'}),
        level: 'error'
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

    logSystemOperation('background_processor_started', {
      source: 'background_processor',
      message: 'Background processor started',
      details: JSON.stringify({
        pollInterval: this.pollInterval,
        hasOpenAIKey,
        hasAnthropicKey,
        defaultProvider: process.env.DEFAULT_LLM_PROVIDER || 'openai'
      }),
      level: 'info'
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

    logSystemOperation('background_processor_stopped', {
      source: 'background_processor',
      message: 'Background processor stopped',
      level: 'info'
    });
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
      
      // Process plan generation queue
      await this.processPlanGenerationQueue();
    } catch (error) {
      console.error('Error in background processor:', error);
      logSystemOperation('background_processor_error', {
        source: 'background_processor',
        message: 'Error in background processor',
        details: JSON.stringify({
          error: error instanceof Error ? error.message : 'Unknown error',
          stack: error instanceof Error ? error.stack : 'No stack trace'
        }),
        level: 'error'
      });
    }
  }
  
  /**
   * Queue a plan generation request for background processing
   */
  public queuePlanGeneration(item: PlanGenerationQueueItem): string {
    // Generate a request ID if not provided
    const requestId = item.requestId || uuidv4();
    const queueItem = { ...item, requestId };
    
    // Add to queue
    this.planGenerationQueue.push(queueItem);
    
    console.log(`Queued plan generation for agent ${item.agentId} with request ID ${requestId}`);
    
    // Log the operation with the new system logger
    logSystemOperation('plan_generation_queued', {
      source: 'plan_generator',
      message: `Queued plan generation for agent ${item.agentId}`,
      details: JSON.stringify({
        agentId: item.agentId,
        requestId,
        isInitialPlan: item.isInitialPlan,
        command: item.command.substring(0, 100) + (item.command.length > 100 ? '...' : '')
      }),
      level: 'info',
      agentId: item.agentId
    });
    
    return requestId;
  }
  
  /**
   * Process the plan generation queue
   */
  private async processPlanGenerationQueue(): Promise<void> {
    if (this.planGenerationQueue.length === 0) {
      return;
    }
    
    // Take the first item from the queue
    const item = this.planGenerationQueue.shift();
    if (!item) return;
    
    try {
      console.log(`Processing plan generation for agent ${item.agentId}`);
      
      // Get agent information
      const agent = await db.agents.getAgentById(item.agentId);
      if (!agent) {
        console.error(`Agent ${item.agentId} not found for plan generation`);
        return;
      }
      
      // Log the operation
      await logOperation('plan_generation_started', {
        agentId: item.agentId,
        requestId: item.requestId,
        isInitialPlan: item.isInitialPlan
      });
      
      // Generate the plan asynchronously
      const { plan, agentNameAndDescription } = await generatePlan(agent, item.command, item.isInitialPlan);
      
      // Save the plan to the database
      const createdPlan = await db.plans.createPlan(plan);
      
      // Update agent if necessary
      const updates: Record<string, any> = { status: AgentStatus.AWAITING_APPROVAL };
      
      // If this is an initial plan or agent metadata was updated, update the agent
      if (agentNameAndDescription) {
        if (item.isInitialPlan || agentNameAndDescription.name !== agent.name) {
          updates.name = agentNameAndDescription.name;
        }
        
        if (item.isInitialPlan || agentNameAndDescription.description !== agent.description) {
          updates.description = agentNameAndDescription.description;
        }
      }
      
      await db.agents.updateAgent(item.agentId, updates);
      
      // Log plan creation
      await logOperation('plan_created_background', {
        agentId: item.agentId,
        planId: createdPlan.id,
        requestId: item.requestId,
        stepCount: createdPlan.steps.length,
        nameUpdated: 'name' in updates && updates.name !== agent.name,
        descriptionUpdated: 'description' in updates && updates.description !== agent.description
      });
      
      // Emit socket events
      this.io.emit('plan:created', {
        agentId: item.agentId,
        planId: createdPlan.id
      });
      
      // If name or description changed, emit update event
      if ('name' in updates || 'description' in updates) {
        this.io.emit('agent:updated', {
          ...agent,
          ...updates
        });
      }
      
    } catch (error) {
      console.error(`Error processing plan generation for agent ${item.agentId}:`, error);
      
      // Update agent status to error
      await db.agents.updateAgent(item.agentId, { status: AgentStatus.ERROR });
      
      // Log the error
      await logOperation('plan_generation_error', {
        agentId: item.agentId,
        requestId: item.requestId,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      
      // Emit socket event for error
      this.io.emit('agent:error', {
        agentId: item.agentId,
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
        const plan = await db.plans.getCurrentPlanForAgent(agent.id as string) as Plan | null;
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
          executeAiProcessing(agent.id as string, planData.id);
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
            const plan = await db.plans.getCurrentPlanForAgent(agent.id as string) as Plan | null;
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