import mysql, { RowDataPacket, OkPacket, ResultSetHeader } from 'mysql2/promise';
import { v4 as uuidv4 } from 'uuid';

// Define a type that combines all possible MySQL query result types
export type QueryResult<T extends RowDataPacket = RowDataPacket> = 
  | T[] 
  | OkPacket 
  | ResultSetHeader[]
  | ResultSetHeader
  | OkPacket[];

// Database connection
const pool = mysql.createPool({
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || 'password',
  database: process.env.DB_NAME || 'times1000',
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
});

// Export the pool directly as well
export { pool };

// Test database connection
async function testConnection() {
  try {
    const connection = await pool.getConnection();
    console.log('Database connection successful');
    connection.release();
  } catch (error) {
    console.error('Database connection failed:', error);
  }
}

// Agent repository
const agents = {
  // Get all agents
  async getAllAgents() {
    try {
      const [rows] = await pool.query<RowDataPacket[]>(`
        SELECT 
          id, name, description, status, 
          capabilities, personality_profile AS personalityProfile,
          settings, created_at AS createdAt, 
          last_active AS updatedAt
        FROM agents
      `);
      
      return rows;
    } catch (error) {
      console.error('Error fetching agents:', error);
      return [];
    }
  },
  
  // Get agent by ID
  async getAgentById(id: string) {
    try {
      const [rows] = await pool.query<RowDataPacket[]>(`
        SELECT 
          id, name, description, status, 
          capabilities, personality_profile AS personalityProfile,
          settings, created_at AS createdAt, 
          last_active AS updatedAt
        FROM agents
        WHERE id = ?
      `, [id]);
      
      // Parse capabilities and settings if they're stored as JSON strings
      if (rows.length > 0) {
        const agent = rows[0];
        if (agent.capabilities && typeof agent.capabilities === 'string') {
          agent.capabilities = JSON.parse(agent.capabilities);
        }
        if (agent.settings && typeof agent.settings === 'string') {
          agent.settings = JSON.parse(agent.settings);
        }
        return agent;
      }
      
      return null;
    } catch (error) {
      console.error(`Error fetching agent ${id}:`, error);
      return null;
    }
  },
  
  // Create a new agent
  async createAgent(agentData: any) {
    try {
      const id = agentData.id || uuidv4();
      const now = new Date();
      
      // Prepare capabilities for storage
      const capabilities = agentData.capabilities 
        ? JSON.stringify(agentData.capabilities)
        : JSON.stringify([]);
      
      // Prepare settings for storage
      const settings = agentData.settings
        ? JSON.stringify(agentData.settings)
        : null;
        
      // Prepare personality profile
      const personalityProfile = agentData.personalityProfile || null;
      
      await pool.query(`
        INSERT INTO agents (
          id, name, description, status, 
          capabilities, personality_profile, settings, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `, [
        id,
        agentData.name,
        agentData.description,
        agentData.status || 'idle',
        capabilities,
        personalityProfile,
        settings,
        now
      ]);
      
      return {
        ...agentData,
        id,
        createdAt: now,
        updatedAt: now
      };
    } catch (error) {
      console.error('Error creating agent:', error);
      throw error;
    }
  },
  
  // Update an agent
  async updateAgent(id: string, updates: Record<string, any>) {
    try {
      let updateQuery = 'UPDATE agents SET ';
      const params = [];
      const updateFields = [];
      
      // Build the update query dynamically
      if (updates.name !== undefined) {
        updateFields.push('name = ?');
        params.push(updates.name);
      }
      
      if (updates.description !== undefined) {
        updateFields.push('description = ?');
        params.push(updates.description);
      }
      
      if (updates.status !== undefined) {
        updateFields.push('status = ?');
        params.push(updates.status);
      }
      
      if (updates.capabilities !== undefined) {
        updateFields.push('capabilities = ?');
        params.push(JSON.stringify(updates.capabilities));
      }
      
      if (updates.personalityProfile !== undefined) {
        updateFields.push('personality_profile = ?');
        params.push(updates.personalityProfile);
      }
      
      if (updates.settings !== undefined) {
        updateFields.push('settings = ?');
        params.push(JSON.stringify(updates.settings));
      }
      
      // last_active will be automatically updated by MySQL
      // No need to set it manually
      
      // Complete the query
      updateQuery += updateFields.join(', ');
      updateQuery += ' WHERE id = ?';
      params.push(id);
      
      // Execute the update
      await pool.query<ResultSetHeader>(updateQuery, params);
      
      // Fetch the updated agent
      return await agents.getAgentById(id);
    } catch (error) {
      console.error(`Error updating agent ${id}:`, error);
      throw error;
    }
  },
  
  // Delete an agent
  async deleteAgent(id: string) {
    try {
      await pool.query<ResultSetHeader>('DELETE FROM agents WHERE id = ?', [id]);
      return true;
    } catch (error) {
      console.error(`Error deleting agent ${id}:`, error);
      return false;
    }
  },
  
  // Get agents by status
  async getAgentsByStatus(status: string) {
    try {
      const [rows] = await pool.query<RowDataPacket[]>(`
        SELECT 
          id, name, description, status, 
          capabilities, personality_profile AS personalityProfile,
          settings, created_at AS createdAt, 
          last_active AS updatedAt
        FROM agents
        WHERE status = ?
      `, [status]);
      
      // Parse capabilities and settings
      return rows.map(agent => {
        // Parse capabilities
        if (agent.capabilities && typeof agent.capabilities === 'string') {
          try {
            agent.capabilities = JSON.parse(agent.capabilities);
          } catch (e) {
            agent.capabilities = [];
          }
        }
        
        // Parse settings
        if (agent.settings && typeof agent.settings === 'string') {
          try {
            agent.settings = JSON.parse(agent.settings);
          } catch (e) {
            agent.settings = {};
          }
        }
        
        return agent;
      });
    } catch (error) {
      console.error(`Error fetching agents with status ${status}:`, error);
      return [];
    }
  }
};

// Plan repository
const plans = {
  // Create a plan
  async createPlan(planData: any) {
    try {
      const id = planData.id || uuidv4();
      const now = new Date();
      
      // Insert the plan
      await pool.query<ResultSetHeader>(`
        INSERT INTO plans (
          id, agent_id, command, description, 
          reasoning, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `, [
        id,
        planData.agentId,
        planData.command,
        planData.description,
        planData.reasoning,
        planData.status || 'awaiting_approval',
        now,
        now
      ]);
      
      // Insert plan steps
      if (planData.steps && planData.steps.length > 0) {
        for (const step of planData.steps) {
          const stepId = step.id || uuidv4();
          await pool.query<ResultSetHeader>(`
            INSERT INTO plan_steps (
              id, plan_id, description, status, 
              result, estimated_duration, position
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
          `, [
            stepId,
            id,
            step.description,
            step.status || 'pending',
            step.result || null,
            step.estimatedDuration || '1m',
            step.position
          ]);
        }
      }
      
      // Return the created plan
      return {
        ...planData,
        id,
        createdAt: now,
        updatedAt: now
      };
    } catch (error) {
      console.error('Error creating plan:', error);
      throw error;
    }
  },
  
  // Get plan by ID
  async getPlanById(id: string) {
    try {
      // Fetch plan
      const [planRows] = await pool.query<RowDataPacket[]>(`
        SELECT 
          id, agent_id AS agentId, command, description, 
          reasoning, status, created_at AS createdAt, 
          updated_at AS updatedAt, follow_up_suggestions
        FROM plans
        WHERE id = ?
      `, [id]);
      
      if (planRows.length === 0) {
        return null;
      }
      
      const plan = planRows[0];
      
      // Fetch steps
      const [stepRows] = await pool.query<RowDataPacket[]>(`
        SELECT 
          id, description, status, result, 
          estimated_duration AS estimatedDuration, 
          position
        FROM plan_steps
        WHERE plan_id = ?
        ORDER BY position
      `, [id]);
      
      // Parse follow-up suggestions if they exist
      if (plan.follow_up_suggestions && typeof plan.follow_up_suggestions === 'string') {
        plan.followUpSuggestions = JSON.parse(plan.follow_up_suggestions);
        plan.hasFollowUp = plan.followUpSuggestions.length > 0;
      } else {
        plan.followUpSuggestions = [];
        plan.hasFollowUp = false;
      }
      
      return {
        ...plan,
        steps: stepRows
      };
    } catch (error) {
      console.error(`Error fetching plan ${id}:`, error);
      return null;
    }
  },
  
  // Get current plan for an agent
  async getCurrentPlanForAgent(agentId: string) {
    try {
      // Get the most recent plan for this agent
      const [planRows] = await pool.query<RowDataPacket[]>(`
        SELECT 
          id, agent_id AS agentId, command, description, 
          reasoning, status, created_at AS createdAt, 
          updated_at AS updatedAt
        FROM plans
        WHERE agent_id = ?
        ORDER BY created_at DESC
        LIMIT 1
      `, [agentId]);
      
      if (planRows.length === 0) {
        return null;
      }
      
      const plan = planRows[0];
      
      // Fetch steps
      const [stepRows] = await pool.query<RowDataPacket[]>(`
        SELECT 
          id, description, status, result, 
          estimated_duration AS estimatedDuration, 
          position
        FROM plan_steps
        WHERE plan_id = ?
        ORDER BY position
      `, [plan.id]);
      
      return {
        ...plan,
        steps: stepRows
      };
    } catch (error) {
      console.error(`Error fetching current plan for agent ${agentId}:`, error);
      return null;
    }
  },
  
  // Update plan status
  async updatePlanStatus(id: string, status: string) {
    try {
      await pool.query<ResultSetHeader>(`
        UPDATE plans 
        SET status = ?, updated_at = ?
        WHERE id = ?
      `, [status, new Date(), id]);
      
      return true;
    } catch (error) {
      console.error(`Error updating plan status ${id}:`, error);
      return false;
    }
  }
};

// Logs repository
const logs = {
  // LLM Logs functions
  llm: {
    // Create a new LLM log entry
    async createLog(logData: any) {
      try {
        const id = logData.id || uuidv4();
        
        await pool.query<ResultSetHeader>(`
          INSERT INTO llm_logs (
            id, agent_id, plan_id, operation, model, provider,
            prompt, response, tokens_prompt, tokens_completion,
            cost_usd, duration_ms, status, error_message, log_type
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `, [
          id,
          logData.agentId || null,
          logData.planId || null,
          logData.operation,
          logData.model,
          logData.provider || 'unknown',
          logData.prompt,
          logData.response || null,
          logData.tokensPrompt || 0,
          logData.tokensCompletion || 0,
          logData.costUsd || null,
          logData.durationMs || 0,
          logData.status,
          logData.errorMessage || null,
          logData.logType || 'llm_api'
        ]);
        
        return { id, ...logData };
      } catch (error) {
        console.error('Error creating LLM log:', error);
        throw error;
      }
    },
    
    // Get all LLM logs with pagination
    async getLogs(page = 1, limit = 20) {
      try {
        const offset = (page - 1) * limit;
        
        const [rows] = await pool.query<RowDataPacket[]>(`
          SELECT 
            id, agent_id AS agentId, plan_id AS planId,
            operation, model, provider, prompt, response,
            tokens_prompt AS tokensPrompt, tokens_completion AS tokensCompletion,
            cost_usd AS costUsd, duration_ms AS durationMs, status, error_message AS errorMessage,
            created_at AS createdAt, log_type AS logType
          FROM llm_logs
          ORDER BY created_at DESC
          LIMIT ? OFFSET ?
        `, [limit, offset]);
        
        // Get total count for pagination
        const [countResult] = await pool.query<RowDataPacket[]>('SELECT COUNT(*) as total FROM llm_logs');
        const totalCount = countResult[0].total;
        
        return {
          logs: rows,
          pagination: {
            page,
            limit,
            totalItems: totalCount,
            totalPages: Math.ceil(totalCount / limit)
          }
        };
      } catch (error) {
        console.error('Error fetching LLM logs:', error);
        return {
          logs: [],
          pagination: {
            page,
            limit,
            totalItems: 0,
            totalPages: 0
          }
        };
      }
    },
    
    // Get LLM logs for a specific agent
    async getLogsByAgentId(agentId: string, page = 1, limit = 20) {
      try {
        const offset = (page - 1) * limit;
        
        const [rows] = await pool.query<RowDataPacket[]>(`
          SELECT 
            id, agent_id AS agentId, plan_id AS planId,
            operation, model, provider, prompt, response,
            tokens_prompt AS tokensPrompt, tokens_completion AS tokensCompletion,
            cost_usd AS costUsd, duration_ms AS durationMs, status, error_message AS errorMessage,
            created_at AS createdAt, log_type AS logType
          FROM llm_logs
          WHERE agent_id = ?
          ORDER BY created_at DESC
          LIMIT ? OFFSET ?
        `, [agentId, limit, offset]);
        
        // Get total count for pagination
        const [countResult] = await pool.query<RowDataPacket[]>(
          'SELECT COUNT(*) as total FROM llm_logs WHERE agent_id = ?',
          [agentId]
        );
        const totalCount = countResult[0].total;
        
        return {
          logs: rows,
          pagination: {
            page,
            limit,
            totalItems: totalCount,
            totalPages: Math.ceil(totalCount / limit)
          }
        };
      } catch (error) {
        console.error(`Error fetching LLM logs for agent ${agentId}:`, error);
        return {
          logs: [],
          pagination: {
            page,
            limit,
            totalItems: 0,
            totalPages: 0
          }
        };
      }
    }
  },
  
  // System Logs functions
  system: {
    // Create a new system log entry
    async createLog(logData: any) {
      try {
        const id = logData.id || uuidv4();
        
        await pool.query<ResultSetHeader>(`
          INSERT INTO system_logs (
            id, source, operation, message, details,
            level, agent_id, plan_id, duration_ms
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        `, [
          id,
          logData.source,
          logData.operation,
          logData.message,
          logData.details || null,
          logData.level || 'info',
          logData.agentId || null,
          logData.planId || null,
          logData.durationMs || 0
        ]);
        
        return { id, ...logData };
      } catch (error) {
        console.error('Error creating system log:', error);
        throw error;
      }
    },
    
    // Get all system logs with pagination
    async getLogs(page = 1, limit = 20) {
      try {
        const offset = (page - 1) * limit;
        
        const [rows] = await pool.query<RowDataPacket[]>(`
          SELECT 
            id, source, operation, message, details,
            level, agent_id AS agentId, plan_id AS planId,
            duration_ms AS durationMs, created_at AS createdAt
          FROM system_logs
          ORDER BY created_at DESC
          LIMIT ? OFFSET ?
        `, [limit, offset]);
        
        // Get total count for pagination
        const [countResult] = await pool.query<RowDataPacket[]>('SELECT COUNT(*) as total FROM system_logs');
        const totalCount = countResult[0].total;
        
        return {
          logs: rows,
          pagination: {
            page,
            limit,
            totalItems: totalCount,
            totalPages: Math.ceil(totalCount / limit)
          }
        };
      } catch (error) {
        console.error('Error fetching system logs:', error);
        return {
          logs: [],
          pagination: {
            page,
            limit,
            totalItems: 0,
            totalPages: 0
          }
        };
      }
    },
    
    // Get system logs for a specific agent
    async getLogsByAgentId(agentId: string, page = 1, limit = 20) {
      try {
        const offset = (page - 1) * limit;
        
        const [rows] = await pool.query<RowDataPacket[]>(`
          SELECT 
            id, source, operation, message, details,
            level, agent_id AS agentId, plan_id AS planId,
            duration_ms AS durationMs, created_at AS createdAt
          FROM system_logs
          WHERE agent_id = ?
          ORDER BY created_at DESC
          LIMIT ? OFFSET ?
        `, [agentId, limit, offset]);
        
        // Get total count for pagination
        const [countResult] = await pool.query<RowDataPacket[]>(
          'SELECT COUNT(*) as total FROM system_logs WHERE agent_id = ?',
          [agentId]
        );
        const totalCount = countResult[0].total;
        
        return {
          logs: rows,
          pagination: {
            page,
            limit,
            totalItems: totalCount,
            totalPages: Math.ceil(totalCount / limit)
          }
        };
      } catch (error) {
        console.error(`Error fetching system logs for agent ${agentId}:`, error);
        return {
          logs: [],
          pagination: {
            page,
            limit,
            totalItems: 0,
            totalPages: 0
          }
        };
      }
    }
  }
};

// Combine all repositories
const db = {
  pool,
  testConnection,
  agents,
  plans,
  // Keep llmLogs for backward compatibility
  llmLogs: {
    createLog: logs.llm.createLog,
    getLogs: logs.llm.getLogs,
    getLogsByAgentId: logs.llm.getLogsByAgentId
  },
  logs
};

export default db;