"""
computer_agent.py - Specialized agent for computer vision-based browser interaction
"""

import logging
from typing import Any, Dict

from agents import Agent, ComputerTool, ModelSettings
from utils.browser_computer import LocalPlaywrightComputer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ComputerAgent")

async def create_computer_agent():
    """Creates a computer agent with vision-based browser interaction capabilities.
    The browser instance is only created when the agent actually uses the ComputerTool."""

    from utils.browser_computer import LocalPlaywrightComputer
    
    # Create a specialized agent for computer vision-based interaction
    agent = Agent(
        name="ComputerAgent",
        instructions="""You are a specialized Computer Agent that handles computer vision-based browser interaction. You use the ComputerTool to perform visual interactions with a web browser.

IMPORTANT: You are the only agent that can use ComputerTool directly. This is an expensive operation that should only be used when the more efficient browser_agent tools are not suitable for a specific task.

CAPABILITIES:
- Visual interaction with browsers using computer vision
- Direct manipulation of UI elements that may be difficult to select with CSS selectors
- Complex interactions that require visual context

HOW TO USE THE COMPUTER TOOL:
1. Use the computer.screenshot() method to see the current state of the browser
2. Use computer.click(x, y) to click at specific coordinates
3. Use computer.type(text) to type text
4. Use computer.navigate(url) to navigate to a URL
5. Use computer.wait() to wait for page elements to load

USAGE GUIDELINES:
- Remember that visual interactions are resource-intensive
- For most web browsing tasks, recommend using browser_agent which uses more efficient methods
- Only use this agent for specialized cases where other methods have failed
- Always provide detailed information about what actions you're taking and why

Always strive to accomplish the user's task efficiently while providing clear explanations of what actions you're taking.
""",
        handoff_description="A specialized agent for computer vision-based browser interaction",
        tools=[
            # Use a lazy-loaded browser computer that only initializes when needed
            ComputerTool(LazyLoadedPlaywrightComputer())
        ],
        # Use computer-use-preview model for ComputerTool
        model="computer-use-preview",
        model_settings=ModelSettings(
            tool_choice="required",
            truncation="auto",
            temperature=0.5  # Lower temperature for more predictable behavior
        )
    )
    
    return agent

# Create a lazy loader for the browser computer to only initialize it when needed
class LazyLoadedPlaywrightComputer:
    """
    A wrapper around LocalPlaywrightComputer that lazily initializes the browser
    only when methods are actually called.
    """
    def __init__(self, headless=False, silent=True):
        self._computer = None
        self.headless = headless
        self.silent = silent
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Ensure the browser is initialized before use"""
        if not self._initialized:
            from utils.browser_computer import LocalPlaywrightComputer
            try:
                self._computer = await LocalPlaywrightComputer(
                    headless=self.headless, 
                    silent=self.silent
                ).__aenter__()
                self._initialized = True
                logger.info("Created browser instance for ComputerAgent (lazy initialization)")
            except Exception as e:
                logger.error(f"Error initializing browser: {e}")
                print(f"Error initializing browser: {e}")
                raise
    
    @property
    def environment(self):
        # This should be accessible without initialization
        return "browser"
    
    @property
    def dimensions(self):
        # This should be accessible without initialization
        return (1024, 768)
    
    async def screenshot(self):
        await self._ensure_initialized()
        return await self._computer.screenshot()
    
    async def click(self, x, y, button="left"):
        await self._ensure_initialized()
        return await self._computer.click(x, y, button)
    
    async def double_click(self, x, y):
        await self._ensure_initialized()
        return await self._computer.double_click(x, y)
    
    async def scroll(self, x, y, scroll_x, scroll_y):
        await self._ensure_initialized()
        return await self._computer.scroll(x, y, scroll_x, scroll_y)
    
    async def type(self, text):
        await self._ensure_initialized()
        return await self._computer.type(text)
    
    async def wait(self, ms=1000):
        await self._ensure_initialized()
        return await self._computer.wait(ms)
    
    async def move(self, x, y):
        await self._ensure_initialized()
        return await self._computer.move(x, y)
    
    async def keypress(self, keys):
        await self._ensure_initialized()
        return await self._computer.keypress(keys)
    
    async def drag(self, path):
        await self._ensure_initialized()
        return await self._computer.drag(path)
    
    async def goto(self, url):
        await self._ensure_initialized()
        return await self._computer.goto(url)
    
    async def navigate(self, url):
        await self._ensure_initialized()
        return await self._computer.navigate(url)
    
    async def cleanup(self):
        """Clean up the browser if it was initialized"""
        if self._initialized and self._computer:
            try:
                await self._computer.__aexit__(None, None, None)
                self._initialized = False
                logger.info("Cleaned up ComputerAgent browser instance")
            except Exception as e:
                logger.error(f"Error cleaning up browser: {e}")
                print(f"Error cleaning up browser: {e}")

async def cleanup_computer_agent(agent):
    """Clean up resources used by the computer agent."""
    try:
        # Get the tool from the agent
        for tool in agent.tools:
            if tool.name == "computer_use_preview":
                computer = tool.computer
                # Check if it's our lazy loaded computer
                if isinstance(computer, LazyLoadedPlaywrightComputer):
                    await computer.cleanup()
                    logger.info("Successfully cleaned up LazyLoadedPlaywrightComputer")
                    return
        
        # Fallback for backward compatibility
        if hasattr(agent, 'browser_computer') and agent.browser_computer is not None:
            await agent.browser_computer.__aexit__(None, None, None)
            logger.info("Cleaned up ComputerAgent browser instance (legacy)")
    except Exception as e:
        logger.error(f"Error cleaning up ComputerAgent browser instance: {e}")
        print(f"Error cleaning up ComputerAgent browser instance: {e}")
