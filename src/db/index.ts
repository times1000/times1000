import mysql, { RowDataPacket } from 'mysql2/promise';
import { Plan, PlanRowData } from '../types/db';

// Create a connection pool
const pool = mysql.createPool({
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '3306', 10),
  user: process.env.DB_USER || 'times1000',
  password: process.env.DB_PASSWORD || 'times1000_password',
  database: process.env.DB_NAME || 'times1000',
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
});

// Test database connection and ensure schema is up to date
const testConnection = async (): Promise<boolean> => {
  try {
    const connection = await pool.getConnection();
    console.log('Successfully connected to MySQL database');
    
    // Check if follow_up_suggestions column exists in plans table
    try {
      const [columnsResult] = await pool.query(`
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'plans' AND COLUMN_NAME = 'follow_up_suggestions'
      `, [process.env.DB_NAME || 'times1000']);
      
      // Safely check if the column exists
      const columns = Array.isArray(columnsResult) ? columnsResult : [];
      
      // If column doesn't exist, add it
      if (columns.length === 0) {
        console.log('Adding missing follow_up_suggestions column to plans table...');
        await pool.query(`
          ALTER TABLE plans 
          ADD COLUMN follow_up_suggestions JSON NULL
        `);
        console.log('Successfully added follow_up_suggestions column');
      }
    } catch (schemaError) {
      console.error('Error checking/updating schema:', schemaError);
    }
    
    connection.release();
    return true;
  } catch (error) {
    console.error('Error connecting to database:', error);
    return false;
  }
};

// Agent-related database operations
const agentOperations = {
  // Get all agents
  getAllAgents: async () => {
    try {
      const [rowsResult] = await pool.query(`
        SELECT 
          id, name, type, description, status, 
          capabilities, created_at AS createdAt, 
          last_active AS lastActive 
        FROM agents
      `);
      
      // Safely handle the result
      const rows = Array.isArray(rowsResult) ? rowsResult : [];
      
      // Convert capabilities from JSON string to array if needed
      return rows.map((agent: any) => ({
        ...agent,
        capabilities: typeof agent.capabilities === 'string' 
          ? JSON.parse(agent.capabilities) 
          : agent.capabilities || []
      }));
    } catch (error) {
      console.error('Error fetching agents:', error);
      throw error;
    }
  },
  
  // Get agent by ID
  getAgentById: async (id: string) => {
    try {
      const [rowsResult] = await pool.query(`
        SELECT 
          id, name, type, description, status, 
          capabilities, created_at AS createdAt, 
          last_active AS lastActive 
        FROM agents 
        WHERE id = ?
      `, [id]);
      
      // Safely handle the result
      const rows = Array.isArray(rowsResult) ? rowsResult : [];
      
      if (rows.length === 0) {
        return null;
      }
      
      const agent = rows[0] as any;
      
      // Handle capabilities safely
      let capabilities = [];
      if (agent && 'capabilities' in agent) {
        if (typeof agent.capabilities === 'string') {
          try {
            capabilities = JSON.parse(agent.capabilities);
          } catch (e) {
            capabilities = [];
          }
        } else if (Array.isArray(agent.capabilities)) {
          capabilities = agent.capabilities;
        }
      }
      
      return {
        ...agent,
        capabilities
      };
    } catch (error) {
      console.error(`Error fetching agent ${id}:`, error);
      throw error;
    }
  },
  
  // Create new agent
  createAgent: async (agent: any) => {
    try {
      const capabilities = JSON.stringify(agent.capabilities || []);
      const personalityProfile = agent.personalityProfile || '';
      const settings = JSON.stringify(agent.settings || {});
      
      // First check if the settings and personalityProfile columns exist
      const [columnsResult] = await pool.query(`
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'agents' 
        AND COLUMN_NAME IN ('settings', 'personality_profile')
      `, [process.env.DB_NAME || 'times1000']);
      
      // Determine if columns exist
      const columns = Array.isArray(columnsResult) ? columnsResult : [];
      const hasSettingsColumn = columns.some((col: any) => col.COLUMN_NAME === 'settings');
      const hasPersonalityColumn = columns.some((col: any) => col.COLUMN_NAME === 'personality_profile');
      
      // Check if the type column still exists in the database
      // This is a transitional check that can be removed later
      const [typeColumnCheck] = await pool.query(`
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'agents' AND COLUMN_NAME = 'type'
      `, [process.env.DB_NAME || 'times1000']);
      
      const typeColumnExists = Array.isArray(typeColumnCheck) && typeColumnCheck.length > 0;
      
      // Prepare the query based on existing columns
      let insertSql = `
        INSERT INTO agents (id, name, description, status, capabilities`;
      let placeholders = `?, ?, ?, ?, ?`;
      const values = [
        agent.id, 
        agent.name, 
        agent.description, 
        agent.status || 'idle',
        capabilities
      ];
      
      // Add personality_profile column if it exists
      if (hasPersonalityColumn) {
        insertSql += `, personality_profile`;
        placeholders += `, ?`;
        values.push(personalityProfile);
      }
      
      // Add settings column if it exists
      if (hasSettingsColumn) {
        insertSql += `, settings`;
        placeholders += `, ?`;
        values.push(settings);
      }
      
      // Handle type column if it still exists (transitional support)
      if (typeColumnExists) {
        insertSql += `, type`;
        placeholders += `, ?`;
        // Use 'custom' as the type for all agents in the unified model
        values.push('custom');
      }
      
      // Close the query
      insertSql += `) VALUES (${placeholders})`;
      
      // Execute the query
      await pool.query(insertSql, values);
      
      return {
        ...agent,
        createdAt: new Date(),
        lastActive: new Date()
      };
    } catch (error) {
      console.error('Error creating agent:', error);
      throw error;
    }
  },
  
  // Update agent
  updateAgent: async (id: string, updates: Record<string, any>) => {
    try {
      const agent = await agentOperations.getAgentById(id);
      if (!agent) {
        throw new Error('Agent not found');
      }
      
      const capabilities = updates.capabilities 
        ? JSON.stringify(updates.capabilities) 
        : undefined;
      
      const updateFields = [];
      const values = [];
      
      if (updates.name !== undefined) {
        updateFields.push('name = ?');
        values.push(updates.name);
      }
      
      if (updates.description !== undefined) {
        updateFields.push('description = ?');
        values.push(updates.description);
      }
      
      if (updates.status !== undefined) {
        updateFields.push('status = ?');
        values.push(updates.status);
      }
      
      if (capabilities !== undefined) {
        updateFields.push('capabilities = ?');
        values.push(capabilities);
      }
      
      // Check if we need to update personality profile or settings
      let hasPersonalityColumn = false;
      let hasSettingsColumn = false;
      
      if (updates.personalityProfile !== undefined || updates.settings !== undefined) {
        try {
          // Check if these columns exist
          const [columnsResult] = await pool.query(`
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'agents' 
            AND COLUMN_NAME IN ('settings', 'personality_profile')
          `, [process.env.DB_NAME || 'times1000']);
          
          // Determine if columns exist
          const columns = Array.isArray(columnsResult) ? columnsResult : [];
          hasPersonalityColumn = columns.some((col: any) => col.COLUMN_NAME === 'personality_profile');
          hasSettingsColumn = columns.some((col: any) => col.COLUMN_NAME === 'settings');
        } catch (error) {
          console.error('Error checking for columns:', error);
        }
      }
      
      // Add personality_profile update if column exists and value provided
      if (hasPersonalityColumn && updates.personalityProfile !== undefined) {
        updateFields.push('personality_profile = ?');
        values.push(updates.personalityProfile);
      }
      
      // Add settings update if column exists and value provided
      if (hasSettingsColumn && updates.settings !== undefined) {
        updateFields.push('settings = ?');
        values.push(JSON.stringify(updates.settings));
      }
      
      if (updateFields.length === 0) {
        return agent;
      }
      
      values.push(id); // Add ID for WHERE clause
      
      await pool.query(`
        UPDATE agents SET ${updateFields.join(', ')}
        WHERE id = ?
      `, values);
      
      return {
        ...agent,
        ...updates,
        lastActive: new Date()
      };
    } catch (error) {
      console.error(`Error updating agent ${id}:`, error);
      throw error;
    }
  },
  
  // Delete agent
  deleteAgent: async (id: string) => {
    try {
      const [result] = await pool.query('DELETE FROM agents WHERE id = ?', [id]);
      
      // Safely check affected rows with type guard
      if (result && typeof result === 'object' && 'affectedRows' in result) {
        return result.affectedRows > 0;
      }
      
      return false;
    } catch (error) {
      console.error(`Error deleting agent ${id}:`, error);
      throw error;
    }
  }
};

// Plan-related database operations
const planOperations = {
  // Create a new plan
  createPlan: async (plan: any) => {
    try {
      await pool.query(`
        INSERT INTO plans (id, agent_id, command, description, reasoning, status)
        VALUES (?, ?, ?, ?, ?, ?)
      `, [
        plan.id,
        plan.agentId,
        plan.command,
        plan.description,
        plan.reasoning,
        plan.status || 'pending'
      ]);
      
      // Insert plan steps if provided
      if (plan.steps && plan.steps.length > 0) {
        const stepValues = plan.steps.map((step: any, index: number) => [
          step.id,
          plan.id,
          step.description,
          step.status || 'pending',
          step.result || null,
          step.estimatedDuration || null,
          index // Position
        ]);
        
        const placeholders = stepValues.map(() => '(?, ?, ?, ?, ?, ?, ?)').join(', ');
        
        await pool.query(`
          INSERT INTO plan_steps (id, plan_id, description, status, result, estimated_duration, position)
          VALUES ${placeholders}
        `, stepValues.flat());
      }
      
      return {
        ...plan,
        createdAt: new Date(),
        updatedAt: new Date()
      };
    } catch (error) {
      console.error('Error creating plan:', error);
      throw error;
    }
  },
  
  // Get current plan for an agent
  getCurrentPlanForAgent: async (agentId: string): Promise<Plan | null> => {
    try {
      // Get the most recent active plan for the agent
      const [planRows] = await pool.query<PlanRowData[]>(`
        SELECT 
          id, agent_id AS agentId, command, description, 
          reasoning, status, created_at AS createdAt, 
          updated_at AS updatedAt
        FROM plans 
        WHERE agent_id = ? AND status IN ('pending', 'approved', 'executing')
        ORDER BY created_at DESC
        LIMIT 1
      `, [agentId]);
      
      // Handle empty result safely
      if (!Array.isArray(planRows) || planRows.length === 0) {
        return null;
      }
      
      const plan = planRows[0] as PlanRowData;
      
      // Get steps for this plan
      const [stepRows] = await pool.query<RowDataPacket[]>(`
        SELECT 
          id, description, status, result, 
          estimated_duration AS estimatedDuration, 
          position
        FROM plan_steps
        WHERE plan_id = ?
        ORDER BY position
      `, [plan.id]);
      
      // Return the plan with properly typed steps
      return {
        ...plan,
        steps: Array.isArray(stepRows) ? stepRows.map(row => ({
          id: row.id,
          description: row.description,
          status: row.status,
          result: row.result,
          estimatedDuration: row.estimatedDuration,
          position: row.position
        })) : []
      } as Plan;
    } catch (error) {
      console.error(`Error fetching current plan for agent ${agentId}:`, error);
      throw error;
    }
  },
  
  // Update plan status
  updatePlanStatus: async (planId: string, status: string) => {
    try {
      const [result] = await pool.query(`
        UPDATE plans SET status = ? WHERE id = ?
      `, [status, planId]);
      
      // Safely check affected rows with type guard
      if (result && typeof result === 'object' && 'affectedRows' in result) {
        return result.affectedRows > 0;
      }
      
      return false;
    } catch (error) {
      console.error(`Error updating plan ${planId} status:`, error);
      throw error;
    }
  },
  
  // Update step status
  updateStepStatus: async (stepId: string, status: string, result?: string) => {
    try {
      const updateFields = ['status = ?'];
      const values = [status];
      
      if (result !== undefined) {
        updateFields.push('result = ?');
        values.push(result);
      }
      
      values.push(stepId); // Add ID for WHERE clause
      
      const [queryResult] = await pool.query(`
        UPDATE plan_steps SET ${updateFields.join(', ')}
        WHERE id = ?
      `, values);
      
      // Safely check affected rows with type guard
      if (queryResult && typeof queryResult === 'object' && 'affectedRows' in queryResult) {
        return queryResult.affectedRows > 0;
      }
      
      return false;
    } catch (error) {
      console.error(`Error updating step ${stepId}:`, error);
      throw error;
    }
  }
};

// Simple logging function
const logOperation = async (operation: string, details: any) => {
  try {
    const timestamp = new Date().toISOString();
    const logEntry = {
      timestamp,
      operation,
      ...details
    };
    
    console.log(`[AI Operation Log] ${timestamp} - ${operation}:`, JSON.stringify(details));
    
    // In a production system, we would save this to a database table
    // Here we're just logging to console
    
    return logEntry;
  } catch (error) {
    console.error('Error logging operation:', error);
  }
};

// LLM logs operations
const llmLogs = {
  // Create a new log entry
  createLog: async (log: {
    operation: string;
    model: string;
    prompt: string;
    response: string | null;
    tokensPrompt: number;
    tokensCompletion: number;
    durationMs: number;
    status: string;
    errorMessage: string | null;
    agentId: string | null;
    planId: string | null;
  }) => {
    try {
      const fields = [
        'operation',
        'model',
        'prompt',
        'response',
        'tokens_prompt',
        'tokens_completion',
        'duration_ms',
        'status',
        'error_message',
        'agent_id',
        'plan_id'
      ];
      
      const values = [
        log.operation,
        log.model,
        log.prompt,
        log.response,
        log.tokensPrompt,
        log.tokensCompletion,
        log.durationMs,
        log.status,
        log.errorMessage,
        log.agentId,
        log.planId
      ];
      
      const [result] = await pool.query(`
        INSERT INTO llm_logs (${fields.join(', ')})
        VALUES (${Array(fields.length).fill('?').join(', ')})
      `, values);
      
      // Safely check insertId with type guard
      if (result && typeof result === 'object' && 'insertId' in result) {
        return { success: true, id: result.insertId };
      }
      
      return { success: true };
    } catch (error) {
      console.error('Error creating log:', error);
      return { success: false };
    }
  },
  
  // Get logs with pagination
  getLogs: async (page = 1, limit = 20) => {
    try {
      const offset = (page - 1) * limit;
      
      // Get logs with pagination
      const [rowsResult] = await pool.query(`
        SELECT 
          id, operation, model, 
          LEFT(prompt, 500) AS prompt_preview,
          LEFT(response, 500) AS response_preview,
          tokens_prompt, tokens_completion, duration_ms,
          status, error_message, agent_id, plan_id,
          created_at
        FROM llm_logs
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
      `, [limit, offset]);
      
      // Get total count for pagination
      const [countResultRaw] = await pool.query('SELECT COUNT(*) as count FROM llm_logs');
      
      // Handle results safely
      const rows = Array.isArray(rowsResult) ? rowsResult : [];
      const countResult = Array.isArray(countResultRaw) ? countResultRaw : [];
      const totalItems = countResult.length > 0 && countResult[0] && 'count' in countResult[0] 
        ? countResult[0].count 
        : 0;
      
      return {
        logs: rows.map((log: any) => ({
          id: log.id,
          operation: log.operation,
          model: log.model,
          promptPreview: log.prompt_preview,
          responsePreview: log.response_preview,
          tokensPrompt: log.tokens_prompt,
          tokensCompletion: log.tokens_completion,
          durationMs: log.duration_ms,
          status: log.status,
          error: log.error_message,
          agentId: log.agent_id,
          planId: log.plan_id,
          createdAt: log.created_at
        })),
        pagination: {
          page,
          limit,
          totalItems,
          totalPages: Math.ceil(totalItems / limit)
        }
      };
    } catch (error) {
      console.error('Error fetching logs:', error);
      throw error;
    }
  },
  
  // Get logs for a specific agent with pagination
  getLogsByAgentId: async (agentId: string, page = 1, limit = 20) => {
    try {
      const offset = (page - 1) * limit;
      
      // Get logs with pagination
      const [rowsResult] = await pool.query(`
        SELECT 
          id, operation, model, 
          LEFT(prompt, 500) AS prompt_preview,
          LEFT(response, 500) AS response_preview,
          tokens_prompt, tokens_completion, duration_ms,
          status, error_message, agent_id, plan_id,
          created_at
        FROM llm_logs
        WHERE agent_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
      `, [agentId, limit, offset]);
      
      // Get total count for pagination
      const [countResultRaw] = await pool.query('SELECT COUNT(*) as count FROM llm_logs WHERE agent_id = ?', [agentId]);
      
      // Handle results safely
      const rows = Array.isArray(rowsResult) ? rowsResult : [];
      const countResult = Array.isArray(countResultRaw) ? countResultRaw : [];
      const totalItems = countResult.length > 0 && countResult[0] && 'count' in countResult[0] 
        ? countResult[0].count 
        : 0;
      
      return {
        logs: rows.map((log: any) => ({
          id: log.id,
          operation: log.operation,
          model: log.model,
          promptPreview: log.prompt_preview,
          responsePreview: log.response_preview,
          tokensPrompt: log.tokens_prompt,
          tokensCompletion: log.tokens_completion,
          durationMs: log.duration_ms,
          status: log.status,
          error: log.error_message,
          agentId: log.agent_id,
          planId: log.plan_id,
          createdAt: log.created_at
        })),
        pagination: {
          page,
          limit,
          totalItems,
          totalPages: Math.ceil(totalItems / limit)
        }
      };
    } catch (error) {
      console.error(`Error fetching logs for agent ${agentId}:`, error);
      throw error;
    }
  }
};

export default {
  pool,
  testConnection,
  agents: agentOperations,
  plans: planOperations,
  logOperation,
  llmLogs
};