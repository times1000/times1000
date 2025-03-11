import fs from 'fs';
import path from 'path';
import { exec, execSync } from 'child_process';
import { promisify } from 'util';
import { v4 as uuidv4 } from 'uuid';
import { LLMMessage, ToolUsage, RequestContext } from './types';
import { logOperation } from '../../api/services/logging-service';

// Promisify exec for async/await usage
const execAsync = promisify(exec);

// Get code execution path from environment
const CODE_EXECUTION_PATH = process.env.CODE_EXECUTION_PATH || './generated-code';
const ENABLE_CODE_EXECUTION = process.env.ENABLE_CODE_EXECUTION === 'true';

// Make sure the directory exists
if (ENABLE_CODE_EXECUTION) {
  try {
    if (!fs.existsSync(CODE_EXECUTION_PATH)) {
      fs.mkdirSync(CODE_EXECUTION_PATH, { recursive: true });
    }
  } catch (error) {
    console.error(`Failed to create code execution directory: ${error}`);
  }
}

/**
 * Generate and execute code using Claude Code CLI
 */
export async function generateAndExecuteCode(
  messages: LLMMessage[],
  context: RequestContext = {}
): Promise<{ result: string; toolUsage: ToolUsage }> {
  if (!ENABLE_CODE_EXECUTION) {
    throw new Error('Code execution is disabled in this environment');
  }

  // Create a unique directory for this code execution
  const sessionId = uuidv4().substring(0, 8);
  const sessionDir = path.join(CODE_EXECUTION_PATH, sessionId);
  
  try {
    // Create the session directory
    fs.mkdirSync(sessionDir, { recursive: true });
    
    // Log the operation
    await logOperation('code_execution_started', {
      sessionId,
      agentId: context.agentId || '',
      planId: context.planId || '',
      operationType: context.operation || 'code_execution'
    });
    
    // Prepare the messages for Claude Code
    const messagesJson = JSON.stringify(messages);
    const messagesFile = path.join(sessionDir, 'messages.json');
    fs.writeFileSync(messagesFile, messagesJson);
    
    // Run Claude Code CLI
    console.log(`Executing Claude Code in directory: ${sessionDir}`);
    
    const claudeCodeCommand = `cd ${sessionDir} && claude -t -m "${messagesFile}"`;
    
    const startTime = Date.now();
    const { stdout, stderr } = await execAsync(claudeCodeCommand, { maxBuffer: 1024 * 1024 * 10 }); // 10MB buffer
    const executionTime = Date.now() - startTime;
    
    // Check for errors
    if (stderr && stderr.length > 0) {
      console.warn('Claude Code warnings/errors:', stderr);
    }
    
    // Count the number of tool calls by looking at file artifacts
    const toolCalls = countToolCalls(sessionDir);
    
    // Calculate tool revenue based on tool calls
    const toolRevenue = toolCalls * 0.001; // $0.001 per tool call (example rate)
    
    // Log completion
    await logOperation('code_execution_completed', {
      sessionId,
      agentId: context.agentId || '',
      planId: context.planId || '',
      executionTime,
      toolCalls,
      toolRevenue
    });
    
    return {
      result: stdout,
      toolUsage: {
        toolCalls,
        toolRevenue
      }
    };
  } catch (error) {
    console.error(`Error executing code with Claude Code: ${error}`);
    
    // Log failure
    await logOperation('code_execution_failed', {
      sessionId,
      agentId: context.agentId || '',
      planId: context.planId || '',
      error: error instanceof Error ? error.message : 'Unknown error'
    });
    
    throw new Error(`Code execution failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Count the number of tool calls by examining the generated artifacts
 */
function countToolCalls(sessionDir: string): number {
  try {
    // Check for tool usage indicators in the session directory
    // This would depend on how Claude Code logs its tool calls
    // For now, we'll look for .log files or tool_usage.json
    
    // Example implementation:
    const files = fs.readdirSync(sessionDir);
    
    // Count relevant files
    let toolCallCount = 0;
    
    for (const file of files) {
      // Count all non-message json files as potential tool calls
      if (file.endsWith('.json') && file !== 'messages.json') {
        toolCallCount++;
      }
      
      // Look for .log files which might indicate tool execution
      if (file.endsWith('.log')) {
        toolCallCount++;
      }
    }
    
    return toolCallCount;
  } catch (error) {
    console.error(`Error counting tool calls: ${error}`);
    return 0;
  }
}

/**
 * Check if Claude Code CLI is available
 */
export function isClaudeCodeAvailable(): boolean {
  if (!ENABLE_CODE_EXECUTION) {
    return false;
  }
  
  try {
    // Try to execute a simple command to check if Claude Code is installed
    execSync('claude --version', { stdio: 'ignore' });
    return true;
  } catch (error) {
    console.warn('Claude Code CLI is not available:', error);
    return false;
  }
}

/**
 * Get the path to generated code files
 */
export function getCodeExecutionPath(): string {
  return CODE_EXECUTION_PATH;
}

/**
 * List available MCP services (detected from environment variables)
 */
export function getAvailableMcpServices(): string[] {
  const services = [];
  
  if (process.env.MCP_MEMORY_URL) {
    services.push('memory');
  }
  
  if (process.env.MCP_FILESYSTEM_URL) {
    services.push('filesystem');
  }
  
  if (process.env.MCP_PLAYWRIGHT_URL) {
    services.push('playwright');
  }
  
  if (process.env.MCP_GITHUB_URL) {
    services.push('github');
  }
  
  return services;
}