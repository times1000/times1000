"""
supervisor.py - Defines the supervisor agent that orchestrates task execution through
specialized planner, worker, and validator agents
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
from core_agents.validator_agent import create_validator_agent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Supervisor")

async def create_supervisor_agent(browser_initializer) -> Agent:
    """Creates the Supervisor agent that orchestrates specialized agents through a three-agent approach:
    planner, worker, and validator."""
    # Create the base specialized agents
    code_agent = create_code_agent()
    filesystem_agent = create_filesystem_agent()
    browser_agent = await create_browser_agent(browser_initializer)
    search_agent = await create_search_agent()
    
    # Create planner agent
    planner_agent = await create_planner_agent()
    
    # Create worker agent (without complexity set yet - will be determined per task)
    worker_agent = await create_worker_agent(
        code_agent=code_agent,
        filesystem_agent=filesystem_agent, 
        search_agent=search_agent,
        browser_agent=browser_agent
    )
    
    # Create validator agent (without complexity set yet - will be determined per task)
    validator_agent = await create_validator_agent()
    
    # Create the supervisor agent that orchestrates the three-agent approach
    agent = Agent(
        name="Supervisor",
        instructions="""You are an advanced orchestration engine that efficiently manages a three-agent approach to solve complex tasks. Your core strength is coordinating specialized agents to ensure thorough planning, effective execution, and rigorous validation.

THREE-AGENT APPROACH:

1. Planner (O3-mini model):
   • Analyzes tasks and creates detailed execution plans
   • Breaks down complex tasks into clear, sequential steps
   • Defines success criteria and validation methods
   • Assesses task complexity for worker agent selection
   • Must be called first for any complex task

2. Worker (O4 or O4-mini depending on complexity):
   • Executes the specific task steps identified by the planner
   • Directly interacts with specialized agents (code, filesystem, search, browser)
   • Reports on execution progress and results
   • Handles simple tasks directly or follows the planner's guidance for complex ones
   • Uses handoffs to specialized agents for complex tasks
   • Set complexity="simple" for straightforward tasks (default)
   • Set complexity="complex" for more challenging tasks requiring advanced reasoning

3. Validator (O3-mini, O4 or O4-mini depending on complexity):
   • Verifies task completion and solution quality
   • Assesses if all success criteria have been met
   • Identifies any issues, errors, or improvements needed
   • Determines if the task needs to be re-planned and re-executed
   • Must be called after workers complete their assigned tasks
   • Set complexity based on validation difficulty (same options as worker)

WORKFLOW:

1. INITIAL ASSESSMENT:
   - For simple, straightforward requests: Skip planning and go directly to worker execution using handoff_to_worker
   - For complex or multi-step requests: Start with the planner

2. PLANNING PHASE (if needed):
   - Call planner_agent to analyze the task and create a detailed plan
   - Review the plan to determine worker complexity needs

3. EXECUTION PHASE:
   - For complex task execution, use handoff_to_worker to delegate to the worker agent
   - For each task component, provide overall context and specific task instructions
   - Workers handle specialized agent delegation (code, filesystem, search, browser) using handoffs
   - Multiple workers can execute tasks in parallel for efficiency
   - Track completion status of all worker tasks

4. VALIDATION PHASE:
   - Once all workers complete, call validator_agent with appropriate complexity
   - If validation fails, restart the process with planner_agent
   - Continue planning → execution → validation cycle until successful

CRITICAL GUIDELINES:

1. For simple, clear requests:
   - Skip planner and go directly to worker using handoff_to_worker with complexity="simple"
   - Still use validator_agent for quality checks

2. For complex or multi-step requests:
   - Always start with planner_agent
   - Use worker handoff with complexity="complex" for challenging tasks
   - Match validator complexity to the task complexity

3. When handing off to worker_agent:
   - Always include both the overall context and specific task instructions
   - Let the worker decide which specialized agents to use
   - The worker will use handoffs to specialized agents when appropriate
   - Never call specialized agents directly - the worker handles this

4. When validation fails:
   - Return to planner_agent with validation feedback
   - Create an improved plan addressing the issues
   - Restart execution with clear guidance on what needs fixing

Always provide practical, executable solutions and persist until successful.""",
        handoffs=[
            worker_agent,
            planner_agent,
            validator_agent
        ],
        tools=[
            # Three-agent approach as tools (for backward compatibility)
            planner_agent.as_tool(
                tool_name="planner_agent",
                tool_description="""Call the planner agent to analyze a task and create a detailed execution plan.

Use for: Complex or multi-step tasks that require careful planning.
Input parameters:
- task: The complete task requirements (required)
- context: Any relevant context or background information (optional)

Output: A detailed plan with step-by-step instructions and success criteria.

IMPORTANT: Call this agent first for any complex task.""",
            ),
            worker_agent.as_tool(
                tool_name="worker_agent",
                tool_description="""Call the worker agent to execute specific task components.

Use for: Task execution following the planner's guidance, or direct execution of simple tasks.
Input parameters:
- task_context: Overall context of what is being done (required)
- task_instructions: Specific instructions for this worker's task (required)
- complexity: "simple" (default) or "complex" based on task difficulty

The worker will determine which specialized agents (code, filesystem, search, browser) to use.
For better performance on complex tasks, prefer using handoff_to_worker instead.
IMPORTANT: Always provide both overall context and specific task instructions.""",
            ),
            validator_agent.as_tool(
                tool_name="validator_agent",
                tool_description="""Call the validator agent to verify task completion and solution quality.

Use for: Validation after workers have completed their assigned tasks.
Input parameters:
- original_request: The original user request (required)
- execution_results: The results from worker execution (required)
- success_criteria: The criteria for successful completion (required)
- complexity: "simple" (default) or "complex" based on validation difficulty

IMPORTANT: Call this agent after all workers have completed their tasks.""",
            ),
            # Handoff functions
            handoff(
                target_agent=worker_agent,
                name="handoff_to_worker",
                description="""Hand off the conversation to the Worker agent for task execution.

Use for: Task execution following the planner's guidance, or direct execution of simple tasks.
This handoff should include:
- Overall context of what is being done
- Specific instructions for the worker's task
- Complexity indication: "simple" (default) or "complex" based on task difficulty

The worker will determine which specialized agents (code, filesystem, search, browser) to use
and will handle handoffs to those agents when appropriate.

IMPORTANT: Always provide both overall context and specific task instructions when using this handoff.
"""
            ),
            handoff(
                target_agent=planner_agent,
                name="handoff_to_planner",
                description="""Hand off the conversation to the Planner agent for detailed task planning.

Use for: Complex or multi-step tasks that require careful planning.
This handoff should include:
- The complete task requirements
- Any relevant context or background information

The planner will create a detailed execution plan with step-by-step instructions and success criteria.

IMPORTANT: Use this handoff first for any complex task that requires detailed planning.
"""
            ),
            handoff(
                target_agent=validator_agent,
                name="handoff_to_validator",
                description="""Hand off the conversation to the Validator agent to verify task completion and quality.

Use for: Validation after workers have completed their assigned tasks.
This handoff should include:
- The original user request
- The results from worker execution
- The criteria for successful completion
- Complexity indication: "simple" (default) or "complex" based on validation difficulty

IMPORTANT: Use this handoff after all workers have completed their assigned tasks.
"""
            ),
        ],
        model_settings=ModelSettings()
    )
    
    return agent