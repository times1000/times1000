"""
browser_service.py - Containerized browser agent service implementation
"""

import os
import asyncio
import logging
from typing import Dict, Any

from services.base_service import BaseAgentService, AgentRequest, run_service
from core_agents.browser_agent import create_browser_agent
from utils.browser_computer import LocalPlaywrightComputer
from agents import Runner, AgentOutput

# Configure logging
logger = logging.getLogger("BrowserService")

class BrowserAgentService(BaseAgentService):
    """Service implementation for the browser agent"""
    
    def __init__(self, agent_type: str):
        """Initialize the service and browser agent"""
        super().__init__(agent_type)
        self.browser_computer = None
        self.agent = None
        self.init_lock = asyncio.Lock()
        self.conversations = {}
        
    async def initialize_agent(self):
        """Initialize the browser agent if not already initialized"""
        async with self.init_lock:
            if self.agent is None:
                logger.info("Initializing browser agent")
                # Initialize the browser
                self.browser_computer = await LocalPlaywrightComputer(headless=True).__aenter__()
                # Create the browser agent
                self.agent = await create_browser_agent(lambda: asyncio.create_task(asyncio.sleep(0)))
                logger.info("Browser agent initialized")
    
    async def process_request(self, request: AgentRequest) -> str:
        """Process a request using the browser agent"""
        # Make sure the agent is initialized
        await self.initialize_agent()
        
        # Prepare input items for the agent
        input_items = [{"content": request.prompt, "role": "user"}]
        
        # Add any conversation context if provided
        if request.conversation_id and request.conversation_id in self.conversations:
            input_items = self.conversations[request.conversation_id]
            # Add the new prompt
            input_items.append({"content": request.prompt, "role": "user"})
        
        # Run the agent
        result = await Runner.run(self.agent, input_items)
        
        # Extract the response
        message = result.output.message
        
        # Store conversation history if needed
        if request.conversation_id:
            self.conversations[request.conversation_id] = result.to_input_list()
        
        return message
    
    async def cleanup(self):
        """Clean up resources when shutting down"""
        if self.browser_computer:
            await self.browser_computer.__aexit__(None, None, None)

# Run the service if executed directly
if __name__ == "__main__":
    agent_type = os.environ.get("AGENT_TYPE", "browser")
    run_service(BrowserAgentService, agent_type)