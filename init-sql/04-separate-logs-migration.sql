-- Create new system_logs table if it doesn't exist
CREATE TABLE IF NOT EXISTS system_logs (
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

-- Add log_type column to the existing llm_api_logs table if it doesn't exist
-- MySQL 8.4 doesn't support IF NOT EXISTS for ADD COLUMN, so we need to do this differently
-- Check if the column exists first, and only add it if it doesn't

-- Check for log_type column
SET @columnExists = (
  SELECT COUNT(*) 
  FROM information_schema.COLUMNS 
  WHERE TABLE_SCHEMA = 'times1000' 
  AND TABLE_NAME = 'llm_api_logs' 
  AND COLUMN_NAME = 'log_type'
);

SET @alterSql = IF(@columnExists = 0, 
  "ALTER TABLE llm_api_logs ADD COLUMN log_type VARCHAR(20) NOT NULL DEFAULT 'llm_api'", 
  'SELECT 1');
PREPARE stmt FROM @alterSql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Check for provider column
SET @columnExists = (
  SELECT COUNT(*) 
  FROM information_schema.COLUMNS 
  WHERE TABLE_SCHEMA = 'times1000' 
  AND TABLE_NAME = 'llm_api_logs' 
  AND COLUMN_NAME = 'provider'
);

SET @alterSql = IF(@columnExists = 0, 
  'ALTER TABLE llm_api_logs ADD COLUMN provider VARCHAR(50) DEFAULT NULL', 
  'SELECT 1');
PREPARE stmt FROM @alterSql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Check if we need to rename the table or if it's already renamed
-- This is a more complex operation that we'll handle with a conditional check
SET @table_exists = (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'times1000' AND table_name = 'llm_api_logs');

-- Only rename if llm_api_logs exists and llm_logs doesn't exist
SET @target_table_exists = (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'times1000' AND table_name = 'llm_logs');

-- Create a prepared statement for conditional execution
SET @rename_sql = IF(@table_exists > 0 AND @target_table_exists = 0, 'RENAME TABLE llm_api_logs TO llm_logs', 'SELECT 1');
PREPARE stmt FROM @rename_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Create a view with the original name for backward compatibility if it doesn't exist
DROP VIEW IF EXISTS llm_api_logs;
CREATE VIEW llm_api_logs AS 
SELECT * FROM llm_logs;

-- Update the existing llm_logs records to have the proper provider
-- Only update records where provider is null to avoid reprocessing
UPDATE llm_logs 
SET provider = 
  CASE 
    WHEN model LIKE 'gpt%' THEN 'openai'
    WHEN model LIKE 'claude%' THEN 'anthropic'
    ELSE 'unknown'
  END
WHERE provider IS NULL;