"""
browser_agent.py - Specialized agent for direct website interaction via browser
with enhanced error handling and retry mechanisms
"""

import logging
from functools import wraps
from typing import Dict, Any, Callable, Awaitable, Optional, TypeVar, cast, Union

from agents import Agent, ComputerTool, ModelSettings

# Custom ToolOutput class since it's not available in the agents package
class ToolOutput:
    """Simple class to represent tool output with possible error"""
    def __init__(self, value: Any = None, error: str = None):
        self.value = value
        self.error = error
from utils.browser_computer import create_browser_tools
from utils import with_retry, RetryStrategy, AgentResult, ConfidenceLevel, ErrorCategory

# Configure logging
logger = logging.getLogger("BrowserAgent")

# Type variable for return values
T = TypeVar('T')

# Create decorated versions of browser tools with retry logic
def create_resilient_browser_tools(browser_tools: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wraps browser tools with retry logic for increased resilience
    
    Args:
        browser_tools: Dictionary of browser tools
        
    Returns:
        Dictionary of wrapped browser tools with retry capabilities
    """
    resilient_tools = {}
    
    for tool_name, tool in browser_tools.items():
        if callable(getattr(tool, 'call', None)):
            original_call = tool.call
            
            # Different tools need different retry strategies
            if "navigate" in tool_name:
                # Navigation needs more retries with longer backoff
                max_retries = 3
                strategy = RetryStrategy.EXPONENTIAL_BACKOFF
                base_delay = 2.0
            elif any(action in tool_name for action in ["click", "fill", "select"]):
                # Interaction tools need quick retries
                max_retries = 2
                strategy = RetryStrategy.LINEAR_BACKOFF
                base_delay = 1.0
            elif "screenshot" in tool_name:
                # Screenshots can retry quickly
                max_retries = 2
                strategy = RetryStrategy.IMMEDIATE
                base_delay = 0.5
            else:
                # Default retry strategy
                max_retries = 2
                strategy = RetryStrategy.LINEAR_BACKOFF
                base_delay = 1.0
            
            @wraps(original_call)
            async def resilient_call(self, *args, _original_call=original_call, 
                                    _max_retries=max_retries, _strategy=strategy, 
                                    _base_delay=base_delay, **kwargs):
                """Wrapped call function with retry logic"""
                
                # Define the function to retry
                async def call_with_args():
                    try:
                        result = await _original_call(self, *args, **kwargs)
                        return result
                    except Exception as e:
                        logger.warning(f"Error in browser tool: {str(e)}")
                        raise
                
                # Apply retry logic
                retry_result = await with_retry(
                    max_retries=_max_retries,
                    retry_strategy=_strategy,
                    base_delay=_base_delay
                )(call_with_args)()
                
                # Convert AgentResult to appropriate return format
                if isinstance(retry_result, AgentResult):
                    if retry_result.success:
                        return retry_result.value
                    else:
                        # For failed operations, include retry information in error message
                        error_msg = f"Failed after {retry_result.retry_count} attempts: {retry_result.error_message}"
                        if retry_result.retry_count > 0:
                            error_msg += f" (Retried {retry_result.retry_count} times)"
                        
                        # Return error details in a format that matches original tool's error format
                        if hasattr(self, 'build_error_output'):
                            return self.build_error_output(error_msg)
                        else:
                            # Generic error format
                            return ToolOutput(error=error_msg)
                else:
                    # Should not happen, but handle just in case
                    return retry_result
            
            # Replace the original call method with our resilient version
            tool.call = resilient_call.__get__(tool, type(tool))
        
        # Add the (potentially) wrapped tool to our result dictionary
        resilient_tools[tool_name] = tool
    
    return resilient_tools

async def create_browser_agent(browser_initializer):
    """Creates a browser agent with navigation and interaction capabilities."""
    # Initialize the browser only when needed
    try:
        browser_computer = await browser_initializer()
        print("Browser computer initialized successfully")
        
        # Get all browser tools 
        base_browser_tools = create_browser_tools(browser_computer)
        
        # Wrap tools with retry logic
        browser_tools = create_resilient_browser_tools(base_browser_tools)
        print("Browser tools created successfully")
    except Exception as e:
        logger.error(f"Error initializing browser or creating tools: {e}")
        print(f"Error initializing browser or creating tools: {e}")
        # Re-raise to fail initialization
        raise
    
    return Agent(
        name="BrowserAgent",
        instructions="""You are a browser interaction expert specializing in website navigation and interaction, with enhanced error handling and recovery capabilities.

CAPABILITIES:
- Navigate to URLs directly using the playwright_navigate tool
- Take screenshots of webpages using the playwright_screenshot tool
- Click on elements using the playwright_click tool
- Fill out forms using the playwright_fill tool
- Make HTTP requests directly using playwright_get, playwright_post, etc.
- Execute JavaScript in the browser using playwright_evaluate
- Automatically retry failed operations with intelligent backoff strategies
- Provide detailed error information and recovery attempts

ENHANCED ERROR HANDLING:
- All tools now feature automatic retry mechanisms with different strategies:
  * Navigation operations retry up to 3 times with exponential backoff
  * Interaction operations (click, fill) retry up to 2 times with linear backoff
  * Screenshot operations retry up to 2 times immediately
- When errors occur, you'll receive information about:
  * The nature of the error (network, timeout, selector not found, etc.)
  * How many retry attempts were made
  * Suggestions for alternative approaches

PREFERRED TOOL ORDER:
1. Use direct Playwright tools whenever possible (playwright_*)
2. Only fall back to ComputerTool when direct tools can't solve your task

DIRECT PLAYWRIGHT TOOLS:
1. playwright_navigate: Navigate to URLs with options
   - Examples:
     * playwright_navigate(url="https://example.com")
     * playwright_navigate(url="https://example.com", timeout=5000)
     * playwright_navigate(url="https://example.com", waitUntil="networkidle")
     * playwright_navigate(url="https://example.com", width=1920, height=1080)
     * playwright_navigate(url="https://example.com", format="markdown")
     * playwright_navigate(url="https://example.com", format="html")

2. playwright_screenshot: Capture screenshots
   - Examples:
     * playwright_screenshot(name="homepage")
     * playwright_screenshot(name="element", selector=".main-content")
     * playwright_screenshot(name="fullpage", fullPage=True)

3. playwright_click: Click elements by CSS selector
   - Examples: 
     * playwright_click(selector=".submit-button")
     * playwright_click(selector="#login-button")
     * playwright_click(selector="button[type='submit']")
     * playwright_click(selector="a[href='/contact']")
     * playwright_click(selector="text=Log In") - clicks element containing this text

4. playwright_iframe_click: Click elements inside iframes
   - Example: playwright_iframe_click(iframeSelector="iframe#content", selector=".button")

5. playwright_fill: Fill form inputs
   - Examples:
     * playwright_fill(selector="#search-input", value="search term")
     * playwright_fill(selector="input[name='username']", value="johndoe")
     * playwright_fill(selector="textarea#comments", value="My detailed comment")

6. playwright_select: Select dropdown options
   - Examples:
     * playwright_select(selector="#dropdown", value="option1")
     * playwright_select(selector="select[name='country']", value="US")

7. playwright_hover: Hover over elements
   - Example: playwright_hover(selector=".hover-menu")

8. playwright_get_text: Get text content from the page or element
   - Example: playwright_get_text()
   - Example: playwright_get_text(selector="#main-content")
   - Example: playwright_get_text(includeHtml=True)
   - Example: playwright_get_text(maxLength=10000)

9. playwright_get_elements: Identifies interactive elements on the page with selector suggestions
   - Example: playwright_get_elements()
   - Example: playwright_get_elements(selectors="button, a.important")
   - This tool is extremely helpful when you need to find clickable elements!

10. playwright_evaluate: Run JavaScript in the browser
   - Example: playwright_evaluate(script="document.querySelector('.hidden').style.display = 'block'")
   - Example: playwright_evaluate(script="return document.querySelectorAll('a').length")
   - Example: playwright_evaluate(script="return Array.from(document.querySelectorAll('button')).map(b => b.textContent)")

11. HTTP Request tools:
   - playwright_get(url="https://api.example.com/data")
   - playwright_post(url="https://api.example.com/submit", value='{"key": "value"}')
   - playwright_put, playwright_patch, playwright_delete

12. Legacy tool (ONLY use if direct tools don't work):
    - ComputerTool: For computer vision-based interaction (use direct tools instead)

IMPORTANT: ALWAYS use the direct Playwright tools (playwright_*) before falling back to the ComputerTool.
The direct tools are faster and more reliable since they don't rely on computer vision.

ELEMENT SELECTION GUIDE:
When trying to interact with elements on a web page, use these selector formats:
1. ID: "#elementId" (e.g., "#submit-button")
2. Class: ".className" (e.g., ".nav-item")
3. Element type: "button", "a", "input", etc.
4. Attribute: "[attribute=value]" (e.g., "[type='submit']", "[href='/contact']")
5. Combining selectors: "button.primary[type='submit']"
6. Text content: "text=Click me" (finds element containing this text)
7. Exact match: "text='Sign up'" (finds element with exactly this text)

If you need to find what elements are available, use these strategies:
1. ALWAYS USE playwright_get_elements() FIRST - this is the easiest way to discover clickable elements!
2. Take a screenshot with playwright_screenshot(name="page") to see the page visually
3. Use playwright_get_text() to get the page content if needed

WORKFLOW FOR INTERACTING WITH ELEMENTS:
1. Navigate to the page: playwright_navigate(url="https://example.com")
2. Take a screenshot: playwright_screenshot(name="page") 
3. Find elements: Use playwright_get_elements() to discover all interactive elements with suggested selectors
4. Interact with elements using the appropriate tool (click, fill, select, etc.)
5. Verify the result with another screenshot or text extraction

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
        tools=[
            # Add all direct Playwright tools
            browser_tools["playwright_navigate"],
            browser_tools["playwright_screenshot"],
            browser_tools["playwright_click"],
            browser_tools["playwright_iframe_click"],
            browser_tools["playwright_fill"],
            browser_tools["playwright_select"],
            browser_tools["playwright_hover"],
            browser_tools["playwright_get_text"],
            browser_tools["playwright_get_elements"],
            browser_tools["playwright_evaluate"],
            browser_tools["playwright_close"],
            
            # HTTP request tools
            browser_tools["playwright_get"],
            browser_tools["playwright_post"],
            browser_tools["playwright_put"],
            browser_tools["playwright_patch"],
            browser_tools["playwright_delete"],
            
            # Legacy tools (only when direct tools don't work)
            ComputerTool(browser_computer)
        ],
        # Use computer-use-preview model when using ComputerTool
        model="computer-use-preview",
        model_settings=ModelSettings(truncation="auto"),
    )