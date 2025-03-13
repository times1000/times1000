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

2. FilesystemAgent: File system operations expert  
   • Capabilities: File/directory creation, organization, and management
   • Perfect for: Project structure, file operations, system queries
   • Can use model="gpt-4o" (full capability) or model="gpt-4o-mini" (faster, cheaper, 70% accuracy)

3. SearchAgent: Information retrieval specialist
   • Capabilities: Web searches, fact-finding, information gathering
   • Perfect for: Finding documentation, research, verifying facts
   • Can use model="gpt-4o" (full capability) or model="gpt-4o-mini" (faster, cheaper, 70% accuracy)

4. BrowserAgent: Website interaction specialist
   • Capabilities: Website navigation, clicking, typing, form filling, HTTP requests, JavaScript execution
   • Perfect for: Website interactions, form filling, UI exploration, API requests
   • IMPORTANT: ALWAYS use for ANY website interaction request 
   • NOTE: Provides goals to the agent, not specific commands - let it determine the best approach
   • Can use model="gpt-4o" (full capability) or model="gpt-4o-mini" (faster, cheaper, 70% accuracy)

WORKFLOW:
1. TASK ANALYSIS:
   - Analyze the task context and instructions provided by the Supervisor
   - Break down the task into actionable steps
   - Identify which specialized agent(s) to use for each step

2. AGENT SELECTION:
   - Choose the most appropriate specialized agent for each step
   - For browser tasks, use the handoff_to_browser_agent function to delegate the entire conversation
   - For other specialized tasks that can use handoffs, prefer handoffs over tools
   - Determine the appropriate model for each specialized agent:
     * Use model="gpt-4o-mini" for simpler tasks (default, faster, 1/10 cost, 70% as accurate)
     * Use model="gpt-4o" for complex tasks requiring high accuracy
   - Provide clear instructions to each agent
   - Include relevant context from your task assignment

3. EXECUTION:
   - Execute steps by delegating to specialized agents using handoffs when possible
   - Review the results from each agent
   - Handle any errors or unexpected results
   - Continue executing steps until the task is complete

4. REPORTING:
   - Provide a clear summary of what was accomplished
   - Include any challenges encountered and how they were resolved
   - Return relevant information or artifacts produced during execution

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

DELEGATION GUIDELINES:
1. For web browsing and website interaction tasks:
   - ALWAYS use handoff_to_browser_agent to delegate the conversation to the browser agent
   - Provide high-level goals with URLs
   - Let the agent determine how to interact with the website

2. For information lookup and web searches:
   - Use search_agent handoff for complex searches
   - Provide clear search queries and what information to extract

3. For file system operations:
   - Use filesystem_agent handoff for complex file operations
   - Provide specific file paths and operations

4. For coding tasks:
   - Use code_agent handoff for complex coding tasks
   - Provide clear requirements and context

CRITICAL INSTRUCTION: 
NEVER respond to the Supervisor with browser instructions in your messages.
ALWAYS delegate ALL browser interactions to the BrowserAgent.
Always prefer using specialized agents rather than trying to implement solutions yourself.
Use handoffs for complex tasks involving specialized agents.
""",
        handoffs=[
            browser_agent,
            code_agent,
            filesystem_agent,
            search_agent
        ],
        tools=[
            # Note: We keep tools available as fallbacks or for simpler tasks
            code_agent.as_tool(
                tool_name="code_agent_tool",
                tool_description="""Delegate coding tasks to a specialized code agent.

Input parameters:
- input: The coding task to perform (required)
- model: "gpt-4o-mini" (default, faster, cheaper, 70% accuracy) or "gpt-4o" (full capability)

Use "gpt-4o-mini" for simple code tasks and "gpt-4o" for complex programming challenges.
For complex tasks, prefer the handoff approach instead of this tool.""",
            ),
            filesystem_agent.as_tool(
                tool_name="filesystem_agent_tool",
                tool_description="""Delegate filesystem operations to a specialized filesystem agent.

Input parameters:
- input: The filesystem operation to perform (required)
- model: "gpt-4o-mini" (default, faster, cheaper, 70% accuracy) or "gpt-4o" (full capability)

Use "gpt-4o-mini" for standard file operations and "gpt-4o" for complex file manipulations.
For complex tasks, prefer the handoff approach instead of this tool.""",
            ),
            search_agent.as_tool(
                tool_name="search_agent_tool",
                tool_description="""Delegate web searches to a specialized search agent.

Input parameters:
- input: The search query or research task (required)
- model: "gpt-4o-mini" (default, faster, cheaper, 70% accuracy) or "gpt-4o" (full capability)

Use "gpt-4o-mini" for basic queries and "gpt-4o" for complex research tasks.
For complex tasks, prefer the handoff approach instead of this tool.""",
            ),
            browser_agent.as_tool(
                tool_name="browser_agent_tool",
                tool_description="""Delegate website interactions to a specialized browser agent.
                
***NOTE: For most browser tasks, prefer the handoff_to_browser_agent handoff instead of this tool***

Input parameters:
- input: The browsing task to perform (required)
- model: "gpt-4o-mini" (default, faster, cheaper, 70% accuracy) or "gpt-4o" (full capability)

This agent handles all web interactions:
- Navigating to websites
- Clicking elements and filling forms
- Screenshots and browser automation
- Content extraction and analysis
- API requests and JavaScript execution

NEVER send browser instructions directly to the user.
ALWAYS use this tool for ANY web browsing tasks if you can't use the handoff approach.
Provide high-level goals, not specific commands.

Use "gpt-4o-mini" for simple browsing and "gpt-4o" for complex interactions.
                """,
            ),
            handoff(
                target_agent=browser_agent,
                name="handoff_to_browser_agent",
                description="""Hand off the conversation to the BrowserAgent for specialized website interaction tasks.
                
***IMPORTANT: ALWAYS use this handoff for ANY web tasks or browser interactions***

This is the preferred way to handle browser-related tasks. The BrowserAgent is specialized for:
- Navigating to websites
- Clicking elements and filling forms
- Screenshots and browser automation
- Content extraction and analysis
- API requests and JavaScript execution

When using this handoff, provide high-level goals rather than specific commands.
Once the browser task is completed, the handoff will return control back to this agent.
                """
            ),
            handoff(
                target_agent=code_agent,
                name="handoff_to_code_agent",
                description="""Hand off the conversation to the CodeAgent for specialized coding tasks.
                
Use this handoff for complex programming tasks such as:
- Writing sophisticated code
- Debugging complex issues
- Code optimization
- Understanding complex codebases

When using this handoff, provide clear context and requirements for the code task.
Once the coding task is completed, the handoff will return control back to this agent.
                """
            ),
            handoff(
                target_agent=filesystem_agent,
                name="handoff_to_filesystem_agent",
                description="""Hand off the conversation to the FilesystemAgent for specialized file operations.
                
Use this handoff for complex file system operations such as:
- Managing multiple files and directories
- Complex file organization
- Project structure setup
- Batch file operations

When using this handoff, provide clear instructions about the file operations needed.
Once the file operations are completed, the handoff will return control back to this agent.
                """
            ),
            handoff(
                target_agent=search_agent,
                name="handoff_to_search_agent",
                description="""Hand off the conversation to the SearchAgent for specialized information retrieval.
                
Use this handoff for complex search operations such as:
- In-depth research on a topic
- Finding detailed documentation
- Gathering information from multiple sources
- Complex fact-checking

When using this handoff, provide clear search queries and information needs.
Once the search task is completed, the handoff will return control back to this agent.
                """
            ),
        ],
        model=model,
        model_settings=ModelSettings()
    )
    
    return agent