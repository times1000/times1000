"""
base_service.py - Base service implementation for containerized agents
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AgentService")

# Request and response models
class AgentRequest(BaseModel):
    """Model for agent requests"""
    prompt: str = Field(..., description="The prompt/task to give to the agent")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context for the task")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for maintaining state")
    timeout: Optional[int] = Field(None, description="Timeout in seconds")

class AgentResponse(BaseModel):
    """Model for agent responses"""
    result: str = Field(..., description="The result/response from the agent")
    success: bool = Field(True, description="Whether the request was successful")
    errors: List[str] = Field(default_factory=list, description="Any errors that occurred")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class BaseAgentService:
    """Base class for all agent services"""
    
    def __init__(self, agent_type: str):
        """Initialize the service with agent type and port from environment"""
        self.agent_type = agent_type
        self.port = int(os.environ.get("SERVICE_PORT", 8000))
        self.app = FastAPI(
            title=f"{self.agent_type.capitalize()} Agent Service",
            description=f"API for the {self.agent_type} agent service",
            version="1.0.0"
        )
        self.setup_routes()
        
    def setup_routes(self):
        """Set up API routes"""
        # Health check endpoint
        @self.app.get("/health")
        async def health():
            return {"status": "ok", "agent_type": self.agent_type}
        
        # Execute agent endpoint
        @self.app.post("/execute", response_model=AgentResponse)
        async def execute(request: AgentRequest):
            try:
                # Process the request
                result = await self.process_request(request)
                return AgentResponse(
                    result=result,
                    success=True,
                    metadata={"agent_type": self.agent_type}
                )
            except Exception as e:
                logger.error(f"Error processing request: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing request: {str(e)}"
                )
    
    async def process_request(self, request: AgentRequest) -> str:
        """
        Process an agent request
        
        This method should be overridden by child classes
        """
        raise NotImplementedError("Child classes must implement process_request")
    
    def run(self):
        """Run the service"""
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=self.port
        )

def run_service(service_class, agent_type: str):
    """Helper function to run a service"""
    service = service_class(agent_type)
    service.run()