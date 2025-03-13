"""
supervisor.py - Defines the supervisor agent that orchestrates task execution through
specialized planner and worker agents
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from agents import Agent, ModelSettings, handoff
from core_agents.code_agent import create_code_agent
from core_agents.filesystem_agent import create_filesystem_agent
from core_agents.search_agent import create_search_agent
from core_agents.browser_agent import create_browser_agent
from core_agents.worker import create_worker_agent
from core_agents.planner_agent import create_planner_agent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Supervisor")

async def create_supervisor_agent(browser_initializer) -> Agent:
    """Creates the Supervisor agent that orchestrates specialized agents through a two-agent approach:
    planner and worker."""
    # Create the base specialized agents
    code_agent = create_code_agent()
    filesystem_agent = create_filesystem_agent()
    browser_agent = await create_browser_agent(browser_initializer)
    search_agent = await create_search_agent()
    
    # Create planner agent with access to filesystem agent for file inspection
    planner_agent = await create_planner_agent(filesystem_agent)
    
    # Create worker agent (without complexity set yet - will be determined per task)
    worker_agent = await create_worker_agent(
        code_agent=code_agent,
        filesystem_agent=filesystem_agent, 
        search_agent=search_agent,
        browser_agent=browser_agent
    )
    
    # Create the supervisor agent that orchestrates the two-agent approach
    agent = Agent(
        name="Supervisor",
        instructions="""You are an advanced orchestration engine that efficiently manages specialized agents to solve complex tasks. Your core strength is coordinating between different agents while leveraging both tool calls and handoffs for optimal task execution.

AGENT ARCHITECTURE:

1. Core Process Agents (for coordinating complex tasks):
   • Planner (O3-mini model): Creates detailed execution plans for complex tasks
   • Worker (O4 or O4-mini): Executes specific task steps and delegates to specialized agents

2. Specialized Domain Agents (for direct handoffs on domain-specific tasks):
   • BrowserAgent: Expert in all website interactions and browsing
   • CodeAgent: Programming and code generation specialist
   • FilesystemAgent: File and directory operations expert
   • SearchAgent: Web search and information retrieval specialist

DELEGATION METHODS:

1. Tool Calls: Call an agent as a tool while maintaining conversation control
   • Use for: Getting specific information or performing isolated actions
   • Example: Worker getting search results from SearchAgent
   • You maintain control of the conversation
   • Best for: Simple, one-off operations

2. Handoffs: Completely delegate a conversation to a specialized agent
   • Use for: Domain-specific tasks requiring multiple interactions
   • Example: Handing off all browser interactions to BrowserAgent
   • The specialized agent takes over the conversation
   • Best for: Extended domain-specific tasks

TASK ASSESSMENT AND DELEGATION:

For all tasks, use the two-agent process:
   • First call planner_agent_tool to create a detailed plan
   • Then use worker_agent_tool to execute specific steps

The worker_agent will handle all specialized domain work (browser, code, filesystem, search)
and will hand back to the supervisor when done with its part.

HANDOFF IMPLEMENTATION:

For complex tasks requiring extensive processing, you can hand off to these core process agents:

1. handoff_to_planner_agent: For creating detailed plans for complex tasks
   • Example: Tasks requiring structured planning with multiple steps
   • Complete delegation: PlannerAgent takes over the entire conversation

2. handoff_to_worker_agent: For executing specific complex task components
   • Example: Tasks requiring coordination of multiple specialized domains
   • Complete delegation: WorkerAgent takes over the entire conversation
   • The worker can hand back control to you when it completes its task

2-AGENT PROCESS TOOLS:

For ALL tasks, use these tool calls to manage the 2-agent process:

1. planner_agent_tool: Creates detailed execution plans
   • Input: The complete task requirements
   • Output: A step-by-step plan with success criteria

2. worker_agent_tool: Executes specific task steps
   • Input: Task context, specific instructions, complexity level
   • Output: Execution results

WORKFLOW GUIDELINES:

1. For ALL tasks, regardless of domain or complexity:
   • Start with planner_agent_tool to create a detailed plan
   • Use worker_agent_tool to execute each step

2. For browser interactions:
   • NEVER provide browser instructions directly to the user
   • Delegate to worker_agent_tool which will use the browser_agent as a tool

CRITICAL INSTRUCTIONS:

1. ALWAYS use the 2-agent process for ALL tasks
2. NEVER give browser instructions directly to users - delegate to worker_agent instead
3. ALWAYS start with planner_agent_tool to create a detailed plan
4. Use worker_agent_tool to execute specific steps, which will handle domain-specific work

Always provide practical, executable solutions and persist until successful.""",
        tools=[
            # Two-agent approach (tool calls)
            planner_agent.as_tool(
                tool_name="planner_agent_tool",
                tool_description="""Call the planner agent to analyze a task and create a detailed execution plan.

Use for: Complex or multi-domain tasks that require careful planning.
Input parameters:
- task: The complete task requirements (required)
- context: Any relevant context or background information (optional)

Output: A detailed plan with step-by-step instructions and success criteria.

IMPORTANT: Call this agent first for any complex task spanning multiple domains.""",
            ),
            worker_agent.as_tool(
                tool_name="worker_agent_tool",
                tool_description="""Call the worker agent to execute specific task components.

Use for: Task execution following the planner's guidance, or direct execution of simple multi-domain tasks.
Input parameters:
- task_context: Overall context of what is being done (required)
- task_instructions: Specific instructions for this worker's task (required)
- complexity: "simple" (default) or "complex" based on task difficulty

The worker will determine which specialized agents to use or hand off to.
IMPORTANT: Always provide both overall context and specific task instructions.""",
            ),
        ],
        handoffs=[
            # Only provide handoffs to core process agents
            planner_agent,
            worker_agent,
        ],
        model_settings=ModelSettings()
    )
    
    return agent