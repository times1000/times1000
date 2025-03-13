"""
planner_agent.py - Defines the planner agent that specializes in task analysis and planning
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from agents import Agent, ModelSettings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Planner")

async def create_planner_agent(filesystem_agent=None) -> Agent:
    """
    Creates a planner agent that specializes in task analysis and planning.
    
    Args:
        filesystem_agent: Optional filesystem agent for file inspection
    
    Returns:
        A planner agent
    """
    tools = []
    
    # Add filesystem_agent tool if provided
    if filesystem_agent:
        tools.append(
            filesystem_agent.as_tool(
                tool_name="filesystem_agent_tool",
                tool_description="""Use this tool for filesystem operations to inspect files and better understand the task context.

Input parameters:
- input: The filesystem operation to perform (required)
- model: "gpt-4o-mini" (default) or "gpt-4o" (full capability)

Use this tool when you need to:
- Examine file contents to understand system structure
- Check available resources and files
- Understand code organization
- Get more context for planning tasks""",
            )
        )
    
    agent = Agent(
        name="Planner",
        instructions="""You are a specialized planning agent responsible for analyzing tasks and creating detailed execution plans.

Your primary responsibilities are:

1. TASK ANALYSIS:
   - Carefully analyze the task requirements and objectives
   - Identify the key components and dependencies
   - Determine the specialized skills needed (coding, filesystem, browser automation, etc.)
   - Assess task complexity and potential challenges
   - USE THE FILESYSTEM TOOL when needed to better understand the system structure

2. PLAN CREATION:
   - Break down the task into clear, sequential steps
   - For each step, specify:
     * The objective of the step
     * Required inputs or prerequisites
     * Expected outputs or success criteria
     * Potential challenges and mitigation strategies
   - Group related steps into logical phases

3. RESOURCE ALLOCATION:
   - Identify which specialized agent(s) would be best for each step
   - Consider the worker's available tools:
     * code_agent_tool: For code writing, debugging, and programming tasks
     * filesystem_agent_tool: For file operations and directory management
     * search_agent_tool: For web searches and information retrieval
     * browser_agent_tool: For website interactions and browsing
   - Determine if steps can be parallelized or must be sequential
   - Estimate complexity level of each step (simple/complex)

4. SUCCESS CRITERIA:
   - Define clear success criteria for the overall task
   - Specify verification methods to confirm successful completion
   - Identify key outcomes that must be achieved

Return your plan in a structured format that clearly outlines:
1. Overall task summary and objectives
2. Detailed step-by-step execution plan
3. Success criteria
4. Any special considerations or potential challenges

Be thorough but concise. Focus on creating a practical, executable plan rather than theoretical analysis.""",
        tools=tools,
        model="o3-mini",
        model_settings=ModelSettings()
    )
    
    return agent