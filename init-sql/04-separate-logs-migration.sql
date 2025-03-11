-- Create new system_logs table
CREATE TABLE system_logs (
  id VARCHAR(36) PRIMARY KEY,
  source VARCHAR(50) NOT NULL,
  operation VARCHAR(100) NOT NULL,
  message TEXT,
  details TEXT,
  level VARCHAR(20) NOT NULL DEFAULT 'info',
  agent_id VARCHAR(36),
  plan_id VARCHAR(36),
  duration_ms INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL,
  FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE SET NULL
);

-- Add log_type column to the existing llm_api_logs table
-- This helps with backward compatibility
ALTER TABLE llm_api_logs
ADD COLUMN log_type VARCHAR(20) NOT NULL DEFAULT 'llm_api',
ADD COLUMN provider VARCHAR(50) DEFAULT NULL;

-- Rename the llm_api_logs table to avoid breaking existing code
-- We'll create a view with the original name
RENAME TABLE llm_api_logs TO llm_logs;

-- Create a view with the original name for backward compatibility
CREATE VIEW llm_api_logs AS 
SELECT * FROM llm_logs;

-- Update the existing llm_logs records to have the proper provider
UPDATE llm_logs 
SET provider = 
  CASE 
    WHEN model LIKE 'gpt%' THEN 'openai'
    WHEN model LIKE 'claude%' THEN 'anthropic'
    ELSE 'unknown'
  END
WHERE provider IS NULL;