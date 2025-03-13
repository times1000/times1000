"""
worker.py - Defines a worker agent that executes specific tasks assigned by the supervisor
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from functools import wraps

from agents import Agent, ModelSettings, handoff
from utils import with_retry, RetryStrategy

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Worker")

async def create_worker_agent(code_agent, filesystem_agent, search_agent, browser_agent, complexity: str = "simple") -> Agent:
    """
    Creates a Worker agent that executes tasks assigned by the supervisor by calling specialized agents.

    Args:
        code_agent: The specialized code agent
        filesystem_agent: The specialized filesystem agent
        search_agent: The specialized search agent
        browser_agent: The specialized browser agent
        complexity: The complexity level of the task ('simple' or 'complex')

    Returns:
        An Agent instance that can execute tasks by delegating to specialized agents
    """
    # Determine model based on complexity
    def _complexity_to_model(complexity: str) -> str:
        """Maps complexity level to appropriate model."""
        if complexity == "complex":
            return "gpt-4o"
        else:  # simple or default
            return "gpt-4o-mini"
            
    model = _complexity_to_model(complexity)
    
    # Apply retry mechanisms for worker agent operations
    async def with_worker_retry(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await with_retry(
                max_retries=2,
                retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                base_delay=1.0
            )(func)(*args, **kwargs)
        return wrapper
    
    # Create the worker agent
    agent = Agent(
        name="Worker",
        instructions="""You are an advanced Worker agent responsible for executing specific tasks assigned by the Supervisor. Your job is to understand your assigned task context and instructions, and then efficiently leverage specialized agents to accomplish it.

SPECIALIZED AGENTS AT YOUR DISPOSAL:
1. CodeAgent: Programming specialist
   • Capabilities: Writing, debugging, explaining, and modifying code
   • Perfect for: All programming tasks, code modifications, explanations
   • Can use model="gpt-4o" (full capability) or model="gpt-4o-mini" (faster, cheaper, 70% accuracy)
   • Available via tool call for simple or complex operations

2. FilesystemAgent: File system operations expert  
   • Capabilities: File/directory creation, organization, and management
   • Perfect for: Project structure, file operations, system queries
   • Can use model="gpt-4o" (full capability) or model="gpt-4o-mini" (faster, cheaper, 70% accuracy)
   • Available via tool call for simple or complex operations

3. SearchAgent: Information retrieval specialist
   • Capabilities: Web searches, fact-finding, information gathering
   • Perfect for: Finding documentation, research, verifying facts
   • Can use model="gpt-4o" (full capability) or model="gpt-4o-mini" (faster, cheaper, 70% accuracy)
   • Available via tool call for simple or complex queries

4. BrowserAgent: Website interaction specialist
   • Capabilities: Website navigation, clicking, typing, form filling, HTTP requests, JavaScript execution
   • Perfect for: Website interactions, form filling, UI exploration, API requests
   • IMPORTANT: ALWAYS use for ANY website interaction request 
   • NOTE: Provides goals to the agent, not specific commands - let it determine the best approach
   • Can use model="gpt-4o" (full capability) or model="gpt-4o-mini" (faster, cheaper, 70% accuracy)
   • Available via tool call for all web interactions

COMMUNICATION WITH SUPERVISOR:
When you have completed your task or if you need to hand back control to the Supervisor:
- Use handoff_to_supervisor when you've completed your assigned tasks
- Provide a clear summary of what was accomplished before handing off
- Include any relevant information that the Supervisor needs to know

WORKFLOW:
1. TASK ANALYSIS:
   - Analyze the task context and instructions provided by the Supervisor
   - Break down the task into actionable steps
   - Identify which specialized agent(s) to use for each step

2. AGENT SELECTION & TOOL USAGE:
   - Choose the most appropriate specialized agent tool for each step
   - Determine the appropriate model for each specialized agent:
     * Use model="gpt-4o-mini" for simpler tasks (default, faster, 1/10 cost, 70% as accurate)
     * Use model="gpt-4o" for complex tasks requiring high accuracy

3. EXECUTION:
   - Use tools to execute tasks and process the results
   - Handle any errors or unexpected results
   - Continue executing steps until the task is complete
   - For complex multi-step tasks, break them down into individual tool calls

4. HANDOFF BACK TO SUPERVISOR:
   - When your part of the task is complete, hand back to the Supervisor
   - Provide a clear summary of what was accomplished
   - Use handoff_to_supervisor for this purpose

TOOL USAGE GUIDELINES:
Use specialized agent tools for:
- Both simple and complex tasks by breaking down complex tasks into manageable steps
- Maintaining control of the conversation flow
- Processing results before continuing to the next step
- Tasks that span multiple agent domains
- Coordinating work across different specialized domains

For complex multi-step tasks:
- Break them down into a series of tool calls
- Process intermediate results between steps
- Maintain state and context across multiple tool calls
- Coordinate work across different specialized agent tools

MODEL SELECTION GUIDELINES:
Use "gpt-4o-mini" (default) for:
- Simple information retrieval
- Basic code snippets or explanations
- Standard file operations
- Straightforward web interactions
- When speed is more important than perfect accuracy

Use "gpt-4o" for:
- Complex reasoning or problem-solving
- Sophisticated code generation or debugging
- Multi-step or nuanced tasks
- When high accuracy is critical
- Tasks where errors would be costly

CRITICAL INSTRUCTION: 
NEVER respond to the Supervisor with browser instructions in your messages.
ALWAYS use the browser_agent_tool for ALL browser interactions.
For complex tasks, break them down into a series of organized tool calls.
Remember to specify the model parameter when needed based on task complexity.
When you've completed your task, ALWAYS hand back to the supervisor using handoff_to_supervisor.
""",
        tools=[
            # Specialized agents as tools for all tasks
            code_agent.as_tool(
                tool_name="code_agent_tool",
                tool_description="""Use this tool for all coding tasks, both simple and complex.

Input parameters:
- input: The coding task to perform (required)
- model: "gpt-4o-mini" (default, faster, cheaper, 70% accuracy) or "gpt-4o" (full capability)

Use "gpt-4o-mini" for simple code tasks and "gpt-4o" for complex programming challenges.
For complex tasks, break them down into multiple tool calls as needed.""",
            ),
            filesystem_agent.as_tool(
                tool_name="filesystem_agent_tool",
                tool_description="""Use this tool for all filesystem operations, both simple and complex.

Input parameters:
- input: The filesystem operation to perform (required)
- model: "gpt-4o-mini" (default, faster, cheaper, 70% accuracy) or "gpt-4o" (full capability)

Use "gpt-4o-mini" for standard file operations and "gpt-4o" for complex file manipulations.
For complex tasks, break them down into multiple tool calls as needed.""",
            ),
            search_agent.as_tool(
                tool_name="search_agent_tool",
                tool_description="""Use this tool for all web searches and research tasks, both simple and complex.

Input parameters:
- input: The search query or research task (required)
- model: "gpt-4o-mini" (default, faster, cheaper, 70% accuracy) or "gpt-4o" (full capability)

Use "gpt-4o-mini" for basic queries and "gpt-4o" for complex research tasks.
For complex research tasks, break them down into multiple focused search queries as needed.""",
            ),
            browser_agent.as_tool(
                tool_name="browser_agent_tool",
                tool_description="""Use this tool for ALL website interactions, both simple and complex.

Input parameters:
- input: The browsing task to perform (required)
- model: "gpt-4o-mini" (default, faster, cheaper, 70% accuracy) or "gpt-4o" (full capability)

This tool handles all web interactions. For complex tasks, break them down into a series of focused browser interactions.

NEVER send browser instructions directly to the user.
Provide high-level goals, not specific commands.

Use "gpt-4o-mini" for simple browsing and "gpt-4o" for complex interactions.
For multi-step web tasks, make multiple tool calls, tracking progress and state between calls.""",
            ),
        ],
        handoffs=[
            # Add handoff back to supervisor
            Agent(name="Supervisor"),
        ],
        model=model,
        model_settings=ModelSettings()
    )
    
    return agent