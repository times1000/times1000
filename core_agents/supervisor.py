"""
supervisor.py - Defines the supervisor agent that orchestrates specialized agents
with support for parallel execution
"""

import asyncio
import heapq
import logging
from typing import Dict, List, Set, Any, Optional, Tuple, Callable, Awaitable
import uuid
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from agents import Agent
from core_agents.code_agent import create_code_agent
from core_agents.filesystem_agent import create_filesystem_agent
from core_agents.search_agent import create_search_agent
from core_agents.browser_agent import create_browser_agent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ParallelSupervisor")

class TaskPriority(Enum):
    """Priority levels for tasks in the queue"""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3

@dataclass(order=True)
class Task:
    """Task representation for the queue system"""
    priority: TaskPriority
    created_at: datetime = field(compare=False)
    task_id: str = field(compare=False)
    agent_type: str = field(compare=False)
    prompt: str = field(compare=False)
    dependencies: Set[str] = field(default_factory=set, compare=False)
    is_completed: bool = field(default=False, compare=False)
    result: Optional[Any] = field(default=None, compare=False)
    is_running: bool = field(default=False, compare=False)
    
    @property
    def can_execute(self) -> bool:
        """Check if all dependencies are satisfied"""
        return not self.dependencies
    
    def remove_dependency(self, task_id: str) -> None:
        """Remove a dependency once it's completed"""
        if task_id in self.dependencies:
            self.dependencies.remove(task_id)

class TaskAggregator:
    """Handles result aggregation from parallel tasks"""
    
    def __init__(self):
        self.results = {}
        
    def add_result(self, task_id: str, result: Any) -> None:
        """Add a task result to the aggregator"""
        self.results[task_id] = result
        
    def get_results(self) -> Dict[str, Any]:
        """Get all collected results"""
        return self.results
    
    def get_result(self, task_id: str) -> Optional[Any]:
        """Get a specific task result"""
        return self.results.get(task_id)
    
    def summarize_results(self) -> str:
        """Create a summary of all results"""
        summary = []
        for task_id, result in self.results.items():
            summary_text = str(result)
            if len(summary_text) > 100:
                summary_text = summary_text[:97] + "..."
            summary.append(f"Task {task_id}: {summary_text}")
        
        return "\n".join(summary)

class ParallelTaskQueue:
    """Priority-based task queue with dependency tracking"""
    
    def __init__(self, max_concurrent_tasks: int = 3):
        self.task_queue = []  # heapq for priority queue
        self.tasks_by_id = {}  # For quick lookup
        self.max_concurrent_tasks = max_concurrent_tasks
        self.running_tasks = 0
        self.aggregator = TaskAggregator()
        self._lock = asyncio.Lock()
        
    async def add_task(self, 
                 agent_type: str, 
                 prompt: str, 
                 priority: TaskPriority = TaskPriority.MEDIUM,
                 dependencies: Set[str] = None) -> str:
        """Add a new task to the queue"""
        task_id = str(uuid.uuid4())
        
        async with self._lock:
            task = Task(
                priority=priority.value,  # Use enum value for sorting
                created_at=datetime.now(),
                task_id=task_id,
                agent_type=agent_type,
                prompt=prompt,
                dependencies=dependencies or set()
            )
            
            self.tasks_by_id[task_id] = task
            heapq.heappush(self.task_queue, task)
            
        return task_id
    
    async def mark_completed(self, task_id: str, result: Any) -> None:
        """Mark a task as completed and update dependencies"""
        async with self._lock:
            if task_id in self.tasks_by_id:
                task = self.tasks_by_id[task_id]
                task.is_completed = True
                task.result = result
                task.is_running = False
                self.running_tasks -= 1
                
                # Add result to the aggregator
                self.aggregator.add_result(task_id, result)
                
                # Update dependencies for other tasks
                for other_task in self.tasks_by_id.values():
                    other_task.remove_dependency(task_id)
                
                logger.info(f"Task {task_id} completed. Current queue size: {len(self.task_queue)}")
    
    async def get_next_executable_task(self) -> Optional[Task]:
        """Get the next executable task from the queue"""
        async with self._lock:
            if not self.task_queue or self.running_tasks >= self.max_concurrent_tasks:
                return None
            
            # We'll use a more efficient approach that preserves heap order
            # First, find all executable tasks (not completed, not running, with all dependencies met)
            executable_tasks = []
            for i, task in enumerate(self.task_queue):
                if not task.is_completed and not task.is_running and task.can_execute:
                    executable_tasks.append((i, task))
            
            if not executable_tasks:
                return None
                
            # Sort executable tasks by priority (maintaining their original priority order)
            executable_tasks.sort(key=lambda x: x[1].priority)
            
            # Take the highest priority task
            idx, highest_priority_task = executable_tasks[0]
            
            # Remove it from the queue
            self.task_queue[idx] = self.task_queue[-1]
            self.task_queue.pop()
            
            # Only heapify if we're not removing the last element
            if self.task_queue:
                heapq.heapify(self.task_queue)
            
            # Mark as running
            highest_priority_task.is_running = True
            self.running_tasks += 1
            
            return highest_priority_task
    
    async def wait_for_all_tasks(self) -> None:
        """Wait until all tasks are completed"""
        while True:
            async with self._lock:
                if not self.task_queue and self.running_tasks == 0:
                    break
            
            await asyncio.sleep(0.1)
    
    def get_aggregator(self) -> TaskAggregator:
        """Get the result aggregator"""
        return self.aggregator

class ParallelSupervisorAgent:
    """Supervisor agent that can execute tasks in parallel"""
    
    def __init__(self, 
                code_agent: Agent, 
                filesystem_agent: Agent, 
                browser_agent: Agent, 
                search_agent: Agent,
                max_concurrent_tasks: int = 3):
        self.code_agent = code_agent
        self.filesystem_agent = filesystem_agent
        self.browser_agent = browser_agent
        self.search_agent = search_agent
        
        self.name = "ParallelSupervisor"
        self.task_queue = ParallelTaskQueue(max_concurrent_tasks=max_concurrent_tasks)
        
        # Map agent types to their implementations
        self.agent_map = {
            "code": self.code_agent,
            "filesystem": self.filesystem_agent, 
            "browser": self.browser_agent,
            "search": self.search_agent
        }
    
    async def execute_task(self, task: Task) -> Any:
        """Execute a single task using the appropriate agent"""
        agent = self.agent_map.get(task.agent_type)
        if not agent:
            logger.error(f"Unknown agent type: {task.agent_type}")
            return f"Error: Unknown agent type {task.agent_type}"
        
        logger.info(f"Executing task {task.task_id} with agent {task.agent_type}")
        
        try:
            # Use the agents Runner API to execute the task
            from agents import Runner
            # Create input with just the task prompt
            input_items = [{"role": "user", "content": task.prompt}]
            # Run the agent with this input
            result = await Runner.run_async(agent, input_items)
            # Extract the output text
            return result.output
        except Exception as e:
            logger.error(f"Error executing task {task.task_id}: {str(e)}")
            return f"Error: {str(e)}"
    
    async def process_queue(self):
        """Process tasks from the queue"""
        # Use background tasks to run multiple tasks concurrently
        running_tasks = set()
        
        while True:
            # First clean up any finished background tasks
            finished_tasks = {task for task in running_tasks if task.done()}
            running_tasks -= finished_tasks
            
            # Get the next executable task if we have capacity
            if len(running_tasks) < self.max_concurrent_tasks:
                task = await self.task_queue.get_next_executable_task()
                if task:
                    # Create and start a background task
                    bg_task = asyncio.create_task(self._process_task(task))
                    running_tasks.add(bg_task)
            
            # Check if we're done
            async with self.task_queue._lock:
                if not self.task_queue.task_queue and self.task_queue.running_tasks == 0 and not running_tasks:
                    break
                    
            # Avoid tight loop - sleep a short time if no tasks were found
            if not task:
                await asyncio.sleep(0.05)
                
    async def _process_task(self, task: Task):
        """Process a single task in the background"""
        try:
            # Execute the task
            result = await self.execute_task(task)
            
            # Mark as completed
            await self.task_queue.mark_completed(task.task_id, result)
        except Exception as e:
            # If error, mark completed with error message
            error_result = f"Error executing task: {str(e)}"
            logger.error(f"Error executing task {task.task_id}: {str(e)}")
            await self.task_queue.mark_completed(task.task_id, error_result)
    
    async def schedule_task(self, 
                     agent_type: str, 
                     prompt: str, 
                     priority: TaskPriority = TaskPriority.MEDIUM,
                     dependencies: Set[str] = None) -> str:
        """Schedule a new task"""
        return await self.task_queue.add_task(agent_type, prompt, priority, dependencies)
    
    async def execute_with_dependencies(self, tasks: List[Tuple[str, str, Set[str], TaskPriority]]) -> Dict[str, Any]:
        """Execute multiple tasks with dependencies and return all results"""
        # Schedule all tasks
        task_ids = []
        for agent_type, prompt, dependencies, priority in tasks:
            task_id = await self.schedule_task(agent_type, prompt, priority, dependencies)
            task_ids.append(task_id)
        
        # Start the queue processing
        processor = asyncio.create_task(self.process_queue())
        
        # Wait for all tasks to complete
        await self.task_queue.wait_for_all_tasks()
        
        # Make sure processor is done
        if not processor.done():
            processor.cancel()
        
        # Return all results
        return self.task_queue.get_aggregator().get_results()
    
    async def execute(self, prompt: str) -> str:
        """Main execution point for the parallel supervisor"""
        logger.info(f"ParallelSupervisorAgent processing: {prompt[:100]}...")
        
        # Identify tasks in the prompt that can be scheduled in parallel
        tasks_to_schedule = []
        
        # Check for multiple agent requirements in the prompt
        if "filesystem" in prompt.lower() and "search" in prompt.lower():
            # Create tasks for both filesystem and search operations
            filesystem_query = prompt
            search_query = prompt
            
            # Schedule filesystem task
            filesystem_task_id = await self.schedule_task("filesystem", filesystem_query, TaskPriority.MEDIUM)
            tasks_to_schedule.append(filesystem_task_id)
            
            # Schedule search task
            search_task_id = await self.schedule_task("search", search_query, TaskPriority.MEDIUM)
            tasks_to_schedule.append(search_task_id)
            
            logger.info(f"Scheduled parallel filesystem and search tasks: {filesystem_task_id}, {search_task_id}")
        
        elif "code" in prompt.lower() and "browser" in prompt.lower():
            # Create tasks for both code and browser operations
            code_query = prompt
            browser_query = prompt
            
            # Schedule code task
            code_task_id = await self.schedule_task("code", code_query, TaskPriority.MEDIUM)
            tasks_to_schedule.append(code_task_id)
            
            # Schedule browser task
            browser_task_id = await self.schedule_task("browser", browser_query, TaskPriority.MEDIUM)
            tasks_to_schedule.append(browser_task_id)
            
            logger.info(f"Scheduled parallel code and browser tasks: {code_task_id}, {browser_task_id}")
        
        else:
            # For simpler requests, use a single agent based on keyword analysis
            agent_type = "code"  # Default
            if "file" in prompt.lower() or "directory" in prompt.lower():
                agent_type = "filesystem"
            elif "search" in prompt.lower() or "find information" in prompt.lower():
                agent_type = "search"
            elif "navigate" in prompt.lower() or "website" in prompt.lower() or "click" in prompt.lower():
                agent_type = "browser"
            
            # Schedule a single task
            task_id = await self.schedule_task(agent_type, prompt)
            tasks_to_schedule.append(task_id)
            logger.info(f"Scheduled single {agent_type} task: {task_id}")
        
        # Process the queue
        await self.process_queue()
        
        # Get results from all scheduled tasks
        results = []
        for task_id in tasks_to_schedule:
            result = self.task_queue.get_aggregator().get_result(task_id)
            if result:
                results.append(result)
        
        # Combine results if we have multiple
        if len(results) > 1:
            combined_result = "Results from parallel execution:\n\n"
            for i, result in enumerate(results, 1):
                combined_result += f"--- Result {i} ---\n{result}\n\n"
            return combined_result
        elif len(results) == 1:
            return results[0]
        else:
            return "No results available from task execution."
    
    def as_agent(self) -> Agent:
        """Convert to a standard Agent for compatibility"""
        return Agent(
            name=self.name,
            instructions="""You are an advanced orchestration engine that efficiently manages specialized expert agents to solve complex tasks in parallel. Your core strength is breaking down problems into optimal sub-tasks and delegating them to the most appropriate specialized agent.

PARALLEL EXECUTION:
- You can execute multiple tasks simultaneously
- You track dependencies between tasks
- You prioritize tasks based on importance
- You aggregate results from parallel executions

SPECIALIZED AGENTS:
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
   • Perfect for: Direct website interactions, form filling, UI exploration, API requests
   • IMPORTANT: ALWAYS use for ANY website interaction request

WORKFLOW:
1. PLANNING:
   - Analyze the request and break it into parallel executable tasks
   - Define dependencies between tasks
   - Assign priorities to tasks
   - Determine appropriate specialized agents for each task

2. EXECUTION:
   - Execute tasks in parallel respecting dependencies
   - Monitor task execution and handle failures
   - Aggregate results from completed tasks

3. VERIFICATION:
   - Perform final verification of the entire task
   - Address any remaining issues
   - Continue iterating until all success criteria are met

Always provide practical, executable solutions and persist until successful.""",
            tools=[
                # We'll implement these as direct function calls within our agent
                # rather than tool definitions for true parallel execution
            ],
        )

async def create_supervisor_agent(browser_initializer) -> Agent:
    """Creates the Supervisor agent that orchestrates specialized agents as tools.
    
    This implementation now supports true parallel execution capabilities.
    """
    # Create specialized agents
    code_agent = create_code_agent()
    filesystem_agent = create_filesystem_agent()
    browser_agent = await create_browser_agent(browser_initializer)
    search_agent = await create_search_agent()
    
    # Create the parallel supervisor with actual execution capabilities
    parallel_supervisor = ParallelSupervisorAgent(
        code_agent=code_agent,
        filesystem_agent=filesystem_agent,
        browser_agent=browser_agent,
        search_agent=search_agent,
        max_concurrent_tasks=3
    )
    
    # Create an agent wrapper that will delegate to our parallel supervisor
    agent = Agent(
        name="ParallelSupervisor",
        instructions="""You are an advanced orchestration engine that efficiently manages specialized expert agents to solve complex tasks. Your core strength is breaking down problems into optimal sub-tasks and delegating them to the most appropriate specialized agent.

PARALLEL EXECUTION:
- You can run multiple tasks in parallel through the task system
- You intelligently break down tasks to maximize concurrency
- You manage dependencies between tasks
- You aggregate results from parallel executions

SPECIALIZED AGENTS:
1. CodeAgent: Programming specialist
   • Capabilities: Writing, debugging, explaining, and modifying code
   • Tools: run_claude_code (delegates to Claude CLI)
   • Perfect for: All programming tasks, code modifications, explanations

2. FilesystemAgent: File system operations expert  
   • Capabilities: File/directory creation, organization, and management
   • Tools: run_shell_command (executes shell commands)
   • Perfect for: Project structure, file operations, system queries

3. SearchAgent: Information retrieval specialist
   • Capabilities: Web searches, fact-finding, information gathering
   • Tools: WebSearchTool (returns search results with links)
   • Perfect for: Finding documentation, research, verifying facts

4. BrowserAgent: Website interaction specialist
   • Capabilities: Website navigation, clicking, typing, form filling, HTTP requests, JavaScript execution
   • Tools: Direct Playwright tools (playwright_navigate, playwright_click, etc.) with ComputerTool as backup
   • Perfect for: Direct website interactions, form filling, UI exploration, API requests
   • IMPORTANT: ALWAYS use for ANY website interaction request
   • NOTE: Always uses direct playwright_* tools for better speed and reliability

WORKFLOW:
1. PLANNING:
   - Analyze the request and create a step-by-step plan
   - Define success criteria and verification methods for each step
   - Identify which steps can run in parallel and which ones have dependencies
   - Assign appropriate specialized agents to each step
   - Determine priority levels for each task

2. EXECUTION:
   - Execute steps by delegating to specialized agents
   - Run independent tasks in parallel when possible
   - IMPORTANT: Each agent requires a different level of instruction:
     * CodeAgent: Can handle complex, high-level tasks with minimal guidance
     * FilesystemAgent: Needs specific file paths and operations
     * SearchAgent: Needs precise search queries with clear objectives
     * BrowserAgent: Requires explicit step-by-step instructions with specific URLs and exact actions
   - Verify each step's success before proceeding
   - Adjust approach or revise plan if a step fails

3. VERIFICATION:
   - Aggregate results from all parallel tasks
   - Perform final verification of the entire task
   - Address any remaining issues
   - Continue iterating until all success criteria are met

SELF-SUFFICIENCY:
- Work autonomously without user intervention
- Use specialized agents to their full potential
- Try multiple approaches before asking for user help
- Access files through FilesystemAgent, not user requests
- Only request user help as a last resort with specific needs

Always provide practical, executable solutions and persist until successful.""",
        tools=[
            # Specialized agents as tools
            code_agent.as_tool(
                tool_name="code_agent",
                tool_description="Delegate coding tasks to a specialized code agent",
            ),
            filesystem_agent.as_tool(
                tool_name="filesystem_agent",
                tool_description="Delegate filesystem operations to a specialized filesystem agent",
            ),
            search_agent.as_tool(
                tool_name="search_agent",
                tool_description="Delegate web searches to a specialized search agent",
            ),
            browser_agent.as_tool(
                tool_name="browser_agent",
                tool_description="Delegate website interactions to a specialized browser agent with direct Playwright tools for navigation, clicking, form filling, screenshots, HTTP requests, and JavaScript execution",
            ),
        ],
    )
    
    # Replace the standard agent with a wrapped version that uses our parallel execution
    # We can't directly modify the agent's execute method as it doesn't expose it
    # Instead, we'll create a wrapper class that delegates to our parallel supervisor
    
    class ParallelExecutionWrapper:
        def __init__(self, agent, parallel_supervisor):
            self.agent = agent
            self.parallel_supervisor = parallel_supervisor
            self.name = agent.name
            # Add additional attributes from the Agent class to maintain compatibility
            for attr in dir(agent):
                if not attr.startswith('_') and attr not in ['execute', 'as_tool']:
                    try:
                        setattr(self, attr, getattr(agent, attr))
                    except (AttributeError, TypeError):
                        pass
            
        async def execute(self, prompt):
            """Execute with parallel capabilities when possible"""
            try:
                logger.info(f"Using parallel execution for: {prompt[:100]}...")
                return await self.parallel_supervisor.execute(prompt)
            except Exception as e:
                logger.error(f"Parallel execution failed: {str(e)}. Falling back to standard execution.")
                # Use the standard agent via the Runner API since we can't access execute directly
                from agents import Runner
                result = await Runner.run_async(self.agent, [{"role": "user", "content": prompt}])
                return result.output
                
        def as_tool(self, *args, **kwargs):
            """Passthrough to maintain API compatibility"""
            return self.agent.as_tool(*args, **kwargs)
    
    # Create the wrapped agent
    wrapped_agent = ParallelExecutionWrapper(agent, parallel_supervisor)
    
    return wrapped_agent