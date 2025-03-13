"""
browser_agent.py - Specialized agent for direct website interaction via browser
with enhanced error handling and retry mechanisms
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional
from datetime import datetime

from agents import Agent, ModelSettings
from utils.browser_computer import LocalPlaywrightComputer, create_browser_tools
from utils import BrowserSessionContext, AgentContextWrapper

# Configure logging
logger = logging.getLogger("BrowserAgent")

async def create_browser_agent(initial_context: Optional[BrowserSessionContext] = None, context_wrapper: Optional[Dict[str, Any]] = None):
    """
    Creates a browser agent with navigation and interaction capabilities.
    Each agent gets its own dedicated browser instance.
    
    Args:
        initial_context: Optional initial BrowserSessionContext to use
        context_wrapper: Optional context wrapper dictionary that contains a BrowserSessionContext
        
    Returns:
        Browser agent with context management capabilities
    """
    # Create default context if not provided
    if initial_context is None and context_wrapper is None:
        initial_context = BrowserSessionContext(user_id=f"user_{int(time.time())}")
    
    # If context_wrapper is provided, use its context if it's a BrowserSessionContext
    if context_wrapper is not None:
        if isinstance(context_wrapper.get("context"), BrowserSessionContext):
            initial_context = context_wrapper.get("context")
        else:
            # Create a new BrowserSessionContext and update the wrapper
            logger.warning(f"Context in wrapper is not a BrowserSessionContext. Creating a new one.")
            initial_context = BrowserSessionContext(user_id=f"user_{int(time.time())}")
            context_wrapper["context"] = initial_context
    # If no context_wrapper exists but we have an initial_context, create a wrapper
    elif initial_context is not None and context_wrapper is None:
        context_wrapper = {"agent_name": "BrowserAgent", "context": initial_context}
    
    try:
        # Initialize the browser directly
        browser_computer = await LocalPlaywrightComputer(headless=False, silent=True).__aenter__()
        logger.info("Created browser instance for BrowserAgent")
        
        # Store context information
        browser_computer._context = initial_context
        if context_wrapper is not None:
            browser_computer._context_wrapper = context_wrapper

        # Get all browser tools using the browser instance
        browser_tools = create_browser_tools(browser_computer)
        
        # Attach browser_computer to each tool
        for tool in browser_tools.values():
            tool.browser_computer = browser_computer
    except Exception as e:
        logger.error(f"Error creating browser tools: {e}")
        print(f"Error creating browser tools: {e}")
        # Re-raise to fail initialization
        raise

    # Create the agent with context_wrapper property for state persistence
    browser_agent = Agent(
        name="BrowserAgent",
        instructions="""You are a browser interaction expert specializing in website navigation and interaction, with enhanced error handling and recovery capabilities.
        
CONTEXT MANAGEMENT:
- You can maintain state between requests using the context_wrapper parameter
- When navigating to URLs, always pass context_wrapper to playwright_navigate
- This allows persistent cookies and navigation history across requests

CAPABILITIES:
- Navigate to URLs directly using the playwright_navigate tool
- Take screenshots of webpages using the playwright_screenshot tool
- Click on elements using the playwright_click tool
- Fill out forms using the playwright_fill tool
- Press keyboard keys using the playwright_keypress tool
- Make HTTP requests directly using playwright_get, playwright_post, etc.
- Execute JavaScript in the browser using playwright_evaluate
- Get geolocation information using the playwright_get_location tool
- Automatically retry failed operations with intelligent backoff strategies
- Provide detailed error information and recovery attempts

WORKFLOW FOR INTERACTING WITH ELEMENTS:
1. Navigate to the page: playwright_navigate(url="https://example.com")
   - This returns cleaned HTML by default which you can use to identify elements
   - The cleaned HTML removes scripts and empty elements, making it easier to analyze
   - No screenshot is necessary if you can identify elements from this content
2. If needed, take a screenshot: playwright_screenshot(name="page")
3. Find elements using one of these methods:
   - Analyze the cleaned HTML output from playwright_navigate
   - Use playwright_get_elements() to discover all interactive elements with suggested selectors
4. Interact with elements using the appropriate tool (click, fill, select, etc.)
5. Verify the result with either the returned HTML content or another screenshot

ERROR RECOVERY STRATEGIES:
1. For element not found errors:
   - Try alternative selectors (ID, class, text content)
   - Use playwright_get_elements() to find available elements
   - Check if the page has changed with a screenshot

2. For navigation errors:
   - Verify the URL is correctly formatted
   - Try increasing the timeout value
   - Check if the site is accessible

3. For timeout errors:
   - Try using a different waitUntil value (load, domcontentloaded, networkidle)
   - Break down complex actions into smaller steps
   - Check if the page has JavaScript that might be blocking

Always provide detailed error information to the user if an interaction fails after all retries, explaining what you tried, what went wrong, and what alternative approaches could be taken.
""",
        handoff_description="A specialized agent for direct website interaction via browser",
        tools=list(browser_tools.values()),
        model_settings=ModelSettings(
            truncation="auto",
            temperature=0.5,  # Reduced temperature for more deterministic behavior
            tool_choice="required"
        )
    )
    
    # Add the context wrapper as a property of the agent for state persistence
    if context_wrapper is not None:
        browser_agent.context_wrapper = context_wrapper
    
    # Store browser_computer instance with the agent for proper cleanup
    browser_agent.browser_computer = browser_computer
        
    return browser_agent

async def cleanup_browser_agent(agent):
    """Clean up resources used by the browser agent."""
    try:
        # Check for browser_computer on the agent
        if hasattr(agent, 'browser_computer') and agent.browser_computer is not None:
            await agent.browser_computer.__aexit__(None, None, None)
            logger.info("Cleaned up BrowserAgent browser instance")
    except Exception as e:
        logger.error(f"Error cleaning up BrowserAgent browser instance: {e}")
        print(f"Error cleaning up BrowserAgent browser instance: {e}")