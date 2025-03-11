-- Add execution_mode and tool_usage columns to plans table
ALTER TABLE plans
ADD COLUMN execution_mode VARCHAR(50) DEFAULT 'standard' AFTER follow_up_suggestions,
ADD COLUMN tool_usage INT DEFAULT 0 AFTER execution_mode;

-- Add indexes for performance
CREATE INDEX idx_execution_mode ON plans (execution_mode);
CREATE INDEX idx_tool_usage ON plans (tool_usage);

-- Also add execution_mode and tool_usage columns to llm_logs table
ALTER TABLE llm_logs
ADD COLUMN execution_mode VARCHAR(50) DEFAULT NULL AFTER error_message,
ADD COLUMN tool_usage INT DEFAULT 0 AFTER execution_mode,
ADD COLUMN tool_revenue DECIMAL(10, 6) DEFAULT 0 AFTER tool_usage;

-- Add indexes for performance
CREATE INDEX idx_llm_execution_mode ON llm_logs (execution_mode);
CREATE INDEX idx_llm_tool_usage ON llm_logs (tool_usage);