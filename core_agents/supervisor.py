"""
supervisor.py - Defines the supervisor agent that orchestrates task execution through
specialized planner and worker agents
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from agents import Agent, ModelSettings, handoff
from core_agents.worker import create_worker_agent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Supervisor")

async def create_supervisor_agent(browser_initializer) -> Agent:
    """Creates the Supervisor agent that orchestrates specialized agents through a two-agent approach:
    planner and worker."""
    # Create the base specialized agents

    # Create worker agent (without complexity set yet - will be determined per task)
    worker_agent = await create_worker_agent(browser_initializer)

    # Create the supervisor agent that orchestrates the two-agent approach
    agent = Agent(
        name="Supervisor",
        instructions="""You are an advanced orchestration engine that efficiently manages specialized agents to solve complex tasks. Your core strength is coordinating between different workers while leveraging handoffs for optimal task execution.

You need to use one or more workers to accomplish your task. Your primary goal is to ensure that the task is completed successfully, using the most efficient approach possible. You should manage each worker by giving it a general context for the task and specific instructions for its role in the task. If the tasks can be more efficiently run in parallel, you should do so.

Every worker has access to the following tools;
1. CodeAgent: Programming specialist
   • Capabilities: Writing, debugging, explaining, and modifying code
   • Perfect for: All programming tasks, code modifications, explanations

2. FilesystemAgent: File system operations expert
   • Capabilities: File/directory creation, organization, and management
   • Perfect for: Project structure, file operations, system queries

3. SearchAgent: Information retrieval specialist
   • Capabilities: Web searches, fact-finding, information gathering
   • Perfect for: Finding documentation, research, verifying facts

4. BrowserAgent: Website interaction specialist
   • Capabilities: Website navigation, clicking, typing, form filling, HTTP requests, JavaScript execution
   • Perfect for: Website interactions, form filling, UI exploration, API requests

5. ComputerAgent: Computer vision-based interaction specialist
   • Capabilities: Visual browser interaction using computer vision
   • Perfect for: Complex interactions where CSS selectors don't work
   • IMPORTANT: More expensive to use than BrowserAgent - use only when necessary

SELF-SUFFICIENCY PRINCIPLES:
1. Work autonomously without user intervention
2. Use workers to complete tasks, if more information is needed, use a worker to get that information, then another worker to perform the task
3. When operations fail, try alternative approaches by creating another worker with a different prompt
4. Keep going until the task is completed in full
5. Only request user input as a last resort
""",
        tools=[
            worker_agent.as_tool(
                tool_name="worker_agent_tool",
                tool_description="""Call the worker agent to execute specific task components.

Use for: Task execution following the planner's guidance, or direct execution of simple multi-domain tasks.
Input parameters:
- input: Overall context of what is being done and specific instructions for this worker's task (required)
- model: "gpt-4o-mini" (default, faster, cheaper, 70% accuracy) or "gpt-4o" (standard capability) or "o3-mini" (full reasoning, significantly more expensive)

The worker will determine which specialized agents to use or hand off to.
IMPORTANT: Always provide both overall context and specific task instructions.""",
            ),
        ],
        handoffs=[
            worker_agent,
        ],
        model_settings=ModelSettings()
    )

    return agent
