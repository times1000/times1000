"""
computer_agent.py - Specialized agent for computer vision-based browser interaction
"""

import logging
from typing import Any, Dict

from agents import Agent, ComputerTool, ModelSettings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ComputerAgent")

async def create_computer_agent(browser_initializer):
    """Creates a computer agent with vision-based browser interaction capabilities."""

    try:
        browser_computer = await browser_initializer()
    except Exception as e:
        logger.error(f"Error initializing browser or creating tools: {e}")
        print(f"Error initializing browser or creating tools: {e}")
        # Re-raise to fail initialization
        raise

    # Create a specialized agent for computer vision-based interaction
    return Agent(
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
            # The only tool is the ComputerTool which provides computer vision-based interaction
            ComputerTool(browser_computer)
        ],
        # Use computer-use-preview model for ComputerTool
        model="computer-use-preview",
        model_settings=ModelSettings(
            tool_choice="required",
            truncation="auto",
            temperature=0.5  # Lower temperature for more predictable behavior
        )
    )
