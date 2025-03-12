"""
supervisor_service.py - Containerized supervisor agent service implementation
"""

import os
import asyncio
import aiohttp
import logging
import json
from typing import Dict, Any, List, Optional

from services.base_service import BaseAgentService, AgentRequest, AgentResponse, run_service
from pydantic import BaseModel, Field
from fastapi import Body

# Configure logging
logger = logging.getLogger("SupervisorService")

class ServiceConfig:
    """Configuration for agent services"""
    BROWSER_SERVICE_URL = os.environ.get("BROWSER_SERVICE_URL", "http://browser:8001")
    CODE_SERVICE_URL = os.environ.get("CODE_SERVICE_URL", "http://code:8002")
    FILESYSTEM_SERVICE_URL = os.environ.get("FILESYSTEM_SERVICE_URL", "http://filesystem:8003")
    SEARCH_SERVICE_URL = os.environ.get("SEARCH_SERVICE_URL", "http://search:8004")
    
    # Mapping of agent type to service URL
    SERVICE_URLS = {
        "browser": BROWSER_SERVICE_URL,
        "code": CODE_SERVICE_URL,
        "filesystem": FILESYSTEM_SERVICE_URL,
        "search": SEARCH_SERVICE_URL
    }

class Task(BaseModel):
    """Model for a task to be executed by an agent"""
    agent_type: str = Field(..., description="Type of agent to use")
    prompt: str = Field(..., description="Prompt to send to the agent")
    priority: int = Field(default=2, description="Priority (0-3, 0 is highest)")
    dependencies: List[str] = Field(default_factory=list, description="Task IDs this task depends on")

class TaskRequest(BaseModel):
    """Model for a batch task execution request"""
    tasks: List[Task] = Field(..., description="List of tasks to execute")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")

class TaskResult(BaseModel):
    """Model for the result of a task execution"""
    task_id: str = Field(..., description="ID of the task")
    agent_type: str = Field(..., description="Type of agent used")
    result: str = Field(..., description="Result from the agent")
    success: bool = Field(True, description="Whether the task completed successfully")
    errors: List[str] = Field(default_factory=list, description="Errors that occurred")

class TaskResponse(BaseModel):
    """Model for the response to a task execution request"""
    results: Dict[str, TaskResult] = Field(..., description="Results of task execution")
    success: bool = Field(True, description="Whether all tasks completed successfully")
    errors: List[str] = Field(default_factory=list, description="Errors that occurred")

class SupervisorAgentService(BaseAgentService):
    """Service implementation for the supervisor agent"""
    
    def __init__(self, agent_type: str):
        """Initialize the supervisor service"""
        super().__init__(agent_type)
        self.conversations = {}
        self.session = None
        
        # Add additional routes for batch processing
        @self.app.post("/execute_batch", response_model=TaskResponse)
        async def execute_batch(request: TaskRequest = Body(...)):
            try:
                # Process the batch request
                results = await self.process_batch_request(request)
                return TaskResponse(
                    results=results,
                    success=all(result.success for result in results.values())
                )
            except Exception as e:
                logger.error(f"Error processing batch request: {str(e)}")
                return TaskResponse(
                    results={},
                    success=False,
                    errors=[f"Error processing batch request: {str(e)}"]
                )
    
    async def _get_session(self):
        """Get or create an aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def process_request(self, request: AgentRequest) -> str:
        """
        Process a single request by determining the appropriate agent
        and forwarding the request
        """
        # Simple agent selection based on prompt content
        agent_type = "code"  # Default to code agent
        
        if "file" in request.prompt.lower() or "directory" in request.prompt.lower():
            agent_type = "filesystem"
        elif "search" in request.prompt.lower() or "find information" in request.prompt.lower():
            agent_type = "search"
        elif ("navigate" in request.prompt.lower() or "website" in request.prompt.lower() or 
              "click" in request.prompt.lower() or "browse" in request.prompt.lower()):
            agent_type = "browser"
        
        # Forward the request to the appropriate agent service
        return await self._forward_request(agent_type, request)
    
    async def process_batch_request(self, request: TaskRequest) -> Dict[str, TaskResult]:
        """Process a batch of tasks, respecting dependencies"""
        # Assign task IDs if not provided
        tasks_by_id = {}
        task_results = {}
        pending_tasks = []
        
        # Create a dictionary of tasks by ID
        for i, task in enumerate(request.tasks):
            task_id = f"task_{i + 1}"
            tasks_by_id[task_id] = task
            pending_tasks.append((task_id, task))
        
        # Process tasks in dependency order
        while pending_tasks:
            # Find tasks that can be executed (no dependencies or all dependencies satisfied)
            executable_tasks = []
            remaining_tasks = []
            
            for task_id, task in pending_tasks:
                can_execute = True
                for dep_id in task.dependencies:
                    if dep_id not in task_results:
                        can_execute = False
                        break
                
                if can_execute:
                    executable_tasks.append((task_id, task))
                else:
                    remaining_tasks.append((task_id, task))
            
            # If no tasks can be executed, there might be a dependency cycle
            if not executable_tasks and remaining_tasks:
                error_msg = "Dependency cycle detected or missing dependencies"
                for task_id, task in remaining_tasks:
                    task_results[task_id] = TaskResult(
                        task_id=task_id,
                        agent_type=task.agent_type,
                        result=error_msg,
                        success=False,
                        errors=[error_msg]
                    )
                break
            
            # Execute tasks in parallel
            tasks = [
                self._execute_task(task_id, task, request.conversation_id)
                for task_id, task in executable_tasks
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Process results
            for task_id, result in results:
                task_results[task_id] = result
            
            # Update pending tasks
            pending_tasks = remaining_tasks
        
        return task_results
    
    async def _execute_task(self, task_id: str, task: Task, conversation_id: Optional[str]) -> tuple:
        """Execute a single task and return the result"""
        try:
            # Create agent request
            agent_request = AgentRequest(
                prompt=task.prompt,
                conversation_id=conversation_id,
                context={"task_id": task_id}
            )
            
            # Forward to appropriate agent
            result = await self._forward_request(task.agent_type, agent_request)
            
            # Return task result
            return task_id, TaskResult(
                task_id=task_id,
                agent_type=task.agent_type,
                result=result,
                success=True
            )
        except Exception as e:
            logger.error(f"Error executing task {task_id}: {str(e)}")
            return task_id, TaskResult(
                task_id=task_id,
                agent_type=task.agent_type,
                result=f"Error: {str(e)}",
                success=False,
                errors=[str(e)]
            )
    
    async def _forward_request(self, agent_type: str, request: AgentRequest) -> str:
        """Forward a request to the appropriate agent service"""
        if agent_type not in ServiceConfig.SERVICE_URLS:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        service_url = f"{ServiceConfig.SERVICE_URLS[agent_type]}/execute"
        
        session = await self._get_session()
        async with session.post(
            service_url,
            json=request.dict(),
            timeout=request.timeout or 300  # Default 5-minute timeout
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"Error from {agent_type} service: {error_text}")
            
            result = await response.json()
            return result["result"]
    
    async def cleanup(self):
        """Clean up resources when shutting down"""
        if self.session and not self.session.closed:
            await self.session.close()

# Run the service if executed directly
if __name__ == "__main__":
    agent_type = os.environ.get("AGENT_TYPE", "supervisor")
    run_service(SupervisorAgentService, agent_type)