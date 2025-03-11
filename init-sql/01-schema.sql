-- Create agents table
CREATE TABLE agents (
  id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  type VARCHAR(50) NOT NULL,
  description TEXT NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'idle',
  capabilities JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Create plans table
CREATE TABLE plans (
  id VARCHAR(36) PRIMARY KEY,
  agent_id VARCHAR(36) NOT NULL,
  command TEXT NOT NULL,
  description TEXT,
  reasoning TEXT,
  status VARCHAR(50) NOT NULL DEFAULT 'pending',
  follow_up_suggestions JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

-- Create plan_steps table
CREATE TABLE plan_steps (
  id VARCHAR(50) PRIMARY KEY,
  plan_id VARCHAR(36) NOT NULL,
  description TEXT NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'pending',
  result TEXT,
  estimated_duration VARCHAR(20),
  position INT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
);

-- Create llm_api_logs table
CREATE TABLE llm_api_logs (
  id VARCHAR(36) PRIMARY KEY,
  agent_id VARCHAR(36),
  plan_id VARCHAR(36),
  operation VARCHAR(50) NOT NULL,
  model VARCHAR(50) NOT NULL,
  prompt LONGTEXT,
  response LONGTEXT,
  tokens_prompt INT,
  tokens_completion INT,
  cost_usd DECIMAL(10,6),
  duration_ms INT,
  status VARCHAR(20) NOT NULL,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL,
  FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE SET NULL
);