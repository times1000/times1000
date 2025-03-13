"""
core_agents package - Collection of specialized agents for the Times1000 project
"""

import logging

class BaseAgent:
    """Base class for all agents with common functionality."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    def process(self, query, input_data=None):
        """Process a query with optional input data from another agent."""
        self.logger.info(f"Processing query: {query[:100]}...")
        # Implement in subclasses
        return "Not implemented in base class"