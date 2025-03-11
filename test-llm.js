// Simple test script for LLM client
const llm = require('./dist/services/llm');
const db = require('./dist/db').default;

async function testLLMLogger() {
  console.log('Testing LLM Logger...');
  
  try {
    // Test database connection
    await db.testConnection();
    
    // Simply log a dummy request
    await llm.logLLMRequest({
      provider: 'test',
      model: 'test-model',
      operation: 'test-operation',
      prompt: 'This is a test prompt',
      response: 'This is a test response',
      tokenUsage: {
        promptTokens: 10,
        completionTokens: 20,
        totalTokens: 30
      },
      costUsd: 0.001,
      durationMs: 150,
      context: {}
    });
    
    console.log('Successfully logged test LLM request');
    
    // Check if it was saved
    const logs = await db.llmLogs.getLogs(1, 10);
    console.log('Retrieved logs:', logs);
    
    process.exit(0);
  } catch (error) {
    console.error('Error testing LLM logger:', error);
    process.exit(1);
  }
}

// Run the test
testLLMLogger();