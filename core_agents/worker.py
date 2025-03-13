"""
worker.py - Defines a worker agent that executes specific tasks assigned by the supervisor
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from functools import wraps

from agents import Agent, ModelSettings, handoff
from utils import with_retry, RetryStrategy, BrowserSessionContext, AgentContextWrapper

from core_agents.code_agent import create_code_agent
from core_agents.filesystem_agent import create_filesystem_agent
from core_agents.search_agent import create_search_agent
from core_agents.browser_agent import create_browser_agent
from core_agents.computer_agent import create_computer_agent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Worker")

async def create_worker_agent(browser_initializer) -> Agent:
    """
    Creates a Worker agent that executes tasks assigned by the supervisor by calling specialized agents.

    Returns:
        An Agent instance that can execute tasks by delegating to specialized agents
    """
    from utils import BrowserSessionContext
    
    # Create a shared browser session context for both browser agents
    browser_context = BrowserSessionContext(user_id=f"user_{int(time.time())}")

    code_agent = create_code_agent()
    filesystem_agent = create_filesystem_agent()
    search_agent = create_search_agent()
    browser_agent = await create_browser_agent(browser_initializer, initial_context=browser_context)
    computer_agent = await create_computer_agent(browser_initializer)

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
   • Can use model="gpt-4o" (full capability) or model="gpt-4o-mini" (preferred for most tasks - faster, cheaper, 70% accuracy)
   • Available via tool call for simple or complex operations

3. SearchAgent: Information retrieval specialist
   • Capabilities: Web searches, fact-finding, information gathering
   • Perfect for: Finding documentation, research, verifying facts
   • Can use model="gpt-4o" (full capability) or model="gpt-4o-mini" (preferred for most tasks - faster, cheaper, 70% accuracy)
   • Available via tool call for simple or complex queries

4. BrowserAgent: Website interaction specialist
   • Capabilities: Website navigation, clicking, typing, form filling, HTTP requests, JavaScript execution
   • Perfect for: Website interactions, form filling, UI exploration, API requests
   • IMPORTANT: ALWAYS use for ANY website interaction request that can use CSS selectors
   • NOTE: Provides goals to the agent, not specific commands - let it determine the best approach
   • Can use model="gpt-4o" (full capability) or model="gpt-4o-mini" (preferred for most tasks - faster, cheaper, 70% accuracy)
   • Available via tool call for all web interactions

5. ComputerAgent: Computer vision-based interaction specialist
   • Capabilities: Visual browser interaction using computer vision
   • Perfect for: Complex interactions where CSS selectors don't work
   • IMPORTANT: More expensive to use than BrowserAgent - use only when necessary
   • Uses model="computer-use-preview" specifically designed for visual interaction
   • ONLY use when browser_agent has failed with selector-based approaches

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
                tool_description="""Use this tool for ALL website interactions that can use CSS selectors.

Input parameters:
- input: The browsing task to perform (required)
- model: "gpt-4o-mini" (default, faster, cheaper, 70% accuracy) or "gpt-4o" (full capability)

This tool handles all selector-based web interactions and maintains browser state automatically between calls.
The tool tracks visited URLs, navigation history, cookies, and session data.

For complex tasks, break them down into a series of focused browser interactions.

NEVER send browser instructions directly to the user.
Provide high-level goals, not specific commands.

Use "gpt-4o-mini" for simple browsing and "gpt-4o" for complex interactions.
For multi-step web tasks, make multiple tool calls, knowing that session state is maintained across calls.""",
            ),
            computer_agent.as_tool(
                tool_name="computer_agent_tool",
                tool_description="""Use this tool ONLY for computer vision-based browser interactions when CSS selectors don't work.

Input parameters:
- input: The visual browser interaction task to perform (required)

This tool uses computer vision to interact with the browser and is significantly more expensive than browser_agent_tool.
ONLY use this when browser_agent has failed with standard selector-based approaches.

The computer_agent uses a specialized model optimized for vision-based interaction.

This tool helps with:
- Complex visual interactions where selectors are difficult to identify
- Interactive elements generated dynamically or with complex structure
- Situations where clicking at specific coordinates is necessary

Provide clear, high-level goals and let the agent determine how to visually interact with the page.""",
            ),
        ],
        model_settings=ModelSettings(tool_choice="required"),
    )

    return agent
