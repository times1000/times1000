"""
Browser computer implementation using Playwright.
Provides browser automation capabilities for agents to interact with web pages.
"""

import asyncio
import base64
import os
from typing import Literal, Optional, Union, List, Dict, Any

from playwright.async_api import async_playwright, Browser, Page, Playwright, BrowserContext
from markdownify import markdownify
from bs4 import BeautifulSoup
import re

from agents import AsyncComputer, Button, Environment
from agents.tool import function_tool

# Key mapping for keyboard operations
CUA_KEY_TO_PLAYWRIGHT_KEY = {
    "/": "Divide",
    "\\": "Backslash",
    "alt": "Alt",
    "arrowdown": "ArrowDown",
    "arrowleft": "ArrowLeft",
    "arrowright": "ArrowRight",
    "arrowup": "ArrowUp",
    "backspace": "Backspace",
    "capslock": "CapsLock",
    "cmd": "Meta",
    "ctrl": "Control",
    "delete": "Delete",
    "end": "End",
    "enter": "Enter",
    "esc": "Escape",
    "home": "Home",
    "insert": "Insert",
    "option": "Alt",
    "pagedown": "PageDown",
    "pageup": "PageUp",
    "shift": "Shift",
    "space": " ",
    "super": "Meta",
    "tab": "Tab",
    "win": "Meta",
}


class LocalPlaywrightComputer(AsyncComputer):
    """
    A computer implemented using a local Playwright browser.
    Creates and manages a browser instance for web interaction.
    """

    def __init__(self, headless: bool = False, silent: bool = False):
        """Initialize the Playwright computer."""
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self.headless = headless
        self.silent = silent

    @property
    def environment(self) -> Environment:
        return "browser"

    @property
    def dimensions(self) -> tuple[int, int]:
        return (1024, 768)

    # Context manager methods
    async def __aenter__(self):
        """Start the Playwright browser when entering the context."""
        self._playwright = await async_playwright().start()
        
        # Launch browser with appropriate settings
        width, height = self.dimensions
        launch_args = [f"--window-size={width},{height}", "--disable-extensions"]
        
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=launch_args
        )
        
        self._page = await self._browser.new_page()
        await self._page.set_viewport_size({"width": width, "height": height})
        
        if not self.silent:
            print("Browser computer initialized successfully")
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the browser when exiting the context."""
        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            self._page = None
            if not self.silent:
                print("Browser computer closed successfully")
        except Exception as e:
            print(f"Error during browser cleanup: {e}")

    # Required browser navigation methods (names must match what ComputerTool expects)
    async def goto(self, url: str) -> None:
        """Navigate to a URL."""
        if not self._page:
            return
            
        try:
            await self._page.goto(url, timeout=10000)
        except Exception as e:
            print(f"Error navigating to {url}: {e}")

    # Computer interaction methods
    async def screenshot(self) -> str:
        """Capture screenshot of the current page."""
        if not self._page:
            return ""
            
        try:
            png_bytes = await self._page.screenshot(full_page=False)
            return base64.b64encode(png_bytes).decode("utf-8")
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            return ""

    async def click(self, x: int, y: int, button: Button = "left") -> None:
        """Click at a position on the page."""
        if not self._page:
            return
            
        try:
            # Handle special button types
            if button == "back":
                await self._page.go_back()
                return
            if button == "forward":
                await self._page.go_forward()
                return
                
            # Normal click
            playwright_button: Literal["left", "middle", "right"] = "left"
            if button in ("left", "right", "middle"):
                playwright_button = button  # type: ignore
                
            await self._page.mouse.click(x, y, button=playwright_button)
        except Exception as e:
            print(f"Error clicking: {e}")

    async def type(self, text: str) -> None:
        """Type text using the keyboard."""
        if not self._page:
            return
            
        try:
            await self._page.keyboard.type(text)
        except Exception as e:
            print(f"Error typing: {e}")

    async def move(self, x: int, y: int) -> None:
        """Move the mouse to a position."""
        if not self._page:
            return
            
        try:
            await self._page.mouse.move(x, y)
        except Exception as e:
            print(f"Error moving mouse: {e}")

    async def scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        """Scroll the page from a position."""
        if not self._page:
            return
            
        try:
            await self._page.mouse.move(x, y)
            # Use proper parameters instead of string interpolation
            await self._page.evaluate("(scrollX, scrollY) => window.scrollBy(scrollX, scrollY)", 
                                     scroll_x, scroll_y)
        except Exception as e:
            print(f"Error scrolling: {e}")

    async def wait(self, ms: int = 1000) -> None:
        """Wait for a specified time in milliseconds."""
        await asyncio.sleep(ms / 1000)

    # Additional methods for completeness
    async def double_click(self, x: int, y: int) -> None:
        """Double-click at a position."""
        if not self._page:
            return
            
        try:
            await self._page.mouse.dblclick(x, y)
        except Exception as e:
            print(f"Error double-clicking: {e}")

    async def keypress(self, keys: List[str]) -> None:
        """Press one or more keys."""
        if not self._page:
            return
            
        try:
            for key in keys:
                mapped_key = CUA_KEY_TO_PLAYWRIGHT_KEY.get(key.lower(), key)
                await self._page.keyboard.press(mapped_key)
        except Exception as e:
            print(f"Error pressing keys: {e}")

    async def drag(self, path: List[Dict[str, int]]) -> None:
        """Drag the mouse along a path."""
        if not self._page or not path:
            return
            
        try:
            await self._page.mouse.move(path[0]["x"], path[0]["y"])
            await self._page.mouse.down()
            for point in path[1:]:
                await self._page.mouse.move(point["x"], point["y"])
            await self._page.mouse.up()
        except Exception as e:
            print(f"Error dragging: {e}")
            
    # Alias for backward compatibility
    async def navigate(self, url: str) -> None:
        """Alias for goto() for backward compatibility."""
        await self.goto(url)


# Create tools for direct Playwright functionality
def create_browser_tools(browser_computer):
    """Create direct Playwright tools for the browser"""
    
    @function_tool
    async def playwright_navigate(url: str, timeout: Optional[int] = None, 
                           waitUntil: Optional[str] = None, 
                           width: Optional[int] = None, 
                           height: Optional[int] = None,
                           format: Optional[str] = None) -> str:
        """
        Navigate the browser to a specific URL with configurable options.
        
        Args:
            url: The URL to navigate to (should start with http:// or https://)
            timeout: Navigation timeout in milliseconds (default: 10000)
            waitUntil: Navigation wait condition (load, domcontentloaded, networkidle)
            width: Viewport width in pixels
            height: Viewport height in pixels
            format: Optional format for content - "html" (default), "text", or "markdown"
        
        Returns:
            A message indicating successful navigation along with the complete HTML of the page by default
        """
        bc = browser_computer
        if not bc._page:
            return "Error: Browser is not initialized"
            
        if not url:
            return "Error: URL parameter is required"
        
        # Ensure URL has a protocol
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            
        print(f"Attempting to navigate to: {url}")
        
        # Handle optional parameters
        nav_timeout = timeout if timeout is not None else 10000  # Default timeout to 10s
        nav_waitUntil = waitUntil if waitUntil else "load"
        content_format = format.lower() if format else "html"  # Change default to html
        
        print(f"Navigation parameters: timeout={nav_timeout}, waitUntil={nav_waitUntil}, format={content_format}")
        
        # Update viewport if specified
        if width and height:
            try:
                await bc._page.set_viewport_size({"width": width, "height": height})
                print(f"Viewport set to {width}x{height}")
            except Exception as e:
                print(f"Viewport error: {e}")
                return f"Error setting viewport: {e}"
        
        # Navigate to the URL
        try:
            print(f"Calling browser goto with url={url}")
            # Use goto and catch any issues
            try:
                response = await bc._page.goto(url, timeout=nav_timeout, wait_until=nav_waitUntil)
                print(f"Navigation response status: {response.status if response else 'No response'}")
            except Exception as nav_err:
                print(f"Initial navigation error: {type(nav_err).__name__}: {nav_err}")
                # Try with different wait_until option as fallback
                try:
                    print(f"Retrying with 'domcontentloaded' option")
                    response = await bc._page.goto(url, timeout=nav_timeout, wait_until="domcontentloaded")
                    print(f"Fallback navigation response status: {response.status if response else 'No response'}")
                except Exception as fallback_err:
                    print(f"Fallback navigation also failed: {type(fallback_err).__name__}: {fallback_err}")
            
            # Wait a moment for page to stabilize
            await asyncio.sleep(1)
            
            # Get current URL - this should be safe even if navigation had issues
            try:
                # Newer Playwright versions use url as a property, not a method
                current_url = bc._page.url
                if callable(current_url):
                    # For backward compatibility with older Playwright versions
                    current_url = await current_url()
                print(f"Current URL: {current_url}")
            except Exception as url_err:
                print(f"Error getting current URL: {type(url_err).__name__}: {url_err}")
                current_url = url  # Fallback to requested URL
            
            # Get page title - this should be safe even if navigation had issues
            try:
                # Newer Playwright versions use title as a property, not a method
                page_title = bc._page.title
                if callable(page_title):
                    # For backward compatibility with older Playwright versions
                    page_title = await page_title()
                print(f"Page title: {page_title}")
            except Exception as title_err:
                print(f"Error getting page title: {type(title_err).__name__}: {title_err}")
                page_title = "Unknown title"  # Fallback
            
            # Get HTML content directly - this method is more reliable than evaluate
            try:
                html_content = await bc._page.content()
            except Exception as content_err:
                print(f"Error getting page content: {type(content_err).__name__}: {content_err}")
                return f"Navigated to: {current_url} - {page_title}\nUnable to extract page content."
            
            # Process based on requested format
            if content_format == "html" or not content_format:
                # Return full HTML content
                return f"Successfully navigated to: {current_url} - {page_title}\n\nHTML content:\n{html_content}"
                
            elif content_format == "markdown":
                try:
                    # Use BeautifulSoup to find the main content
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Try to get the main content area
                    main_content = None
                    for container in ['article', 'main', '#content', '.content', '#main', '.main']:
                        elements = soup.select(container)
                        if elements:
                            main_content = elements[0]
                            print(f"Found main content container for markdown: {container}")
                            break
                    
                    # If no main content container found, use body
                    if not main_content:
                        main_content = soup.body if soup.body else soup
                    
                    # Remove scripts and styles
                    for script in main_content.find_all(['script', 'style']):
                        script.decompose()
                    
                    # Add title as heading
                    title_md = f"# {page_title}\n\n" if page_title and page_title != "Unknown title" else ""
                    
                    # Convert to markdown with improved settings
                    md_content = markdownify(str(main_content), heading_style="ATX")
                    
                    # Clean up the markdown output
                    md_content = re.sub(r'\n{3,}', '\n\n', md_content)  # Remove excessive newlines
                    
                    content = title_md + md_content
                    
                    # Truncate if too long
                    if len(content) > 5000:
                        preview_content = content[:5000] + "\n\n[Content truncated due to length]"
                    else:
                        preview_content = content
                    
                    return f"Successfully navigated to: {current_url}\n\n{preview_content}"
                except Exception as md_err:
                    print(f"Error converting to markdown: {type(md_err).__name__}: {md_err}")
                    return f"Successfully navigated to: {current_url} - {page_title}\nUnable to convert content to markdown: {md_err}"
            
            elif content_format == "text":  # Only process as text if explicitly requested
                # Extract page content using BeautifulSoup - this approach is more reliable than evaluate
                try:
                    # Parse with BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Try to identify main content containers
                    main_content = None
                    
                    # Look for common content containers
                    for container in ['main', 'article', '#content', '.content', '#main', '.main']:
                        elements = soup.select(container)
                        if elements:
                            main_content = elements[0]
                            print(f"Found main content container: {container}")
                            break
                    
                    # If no main content container found, use body
                    if not main_content:
                        main_content = soup.body if soup.body else soup
                    
                    # Get meaningful text content
                    if main_content:
                        # Remove scripts, styles, and hidden elements
                        for script in main_content.find_all(['script', 'style']):
                            script.decompose()
                        
                        # Get text content 
                        text_content = main_content.get_text(separator='\n', strip=True)
                        
                        # Clean up the text
                        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                        text_content = '\n'.join(lines)
                    else:
                        # Fallback if no meaningful content found
                        text_content = soup.get_text(separator='\n', strip=True)
                    
                    # Truncate if too long
                    if len(text_content) > 2000:
                        preview_text = text_content[:2000] + "...\n[Content truncated due to length]"
                    else:
                        preview_text = text_content
                    
                    # For debugging
                    content_preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
                    print(f"Content preview: {content_preview}")
                    
                    return f"Successfully navigated to: {current_url} - {page_title}\n\nPage content:\n{preview_text}"
                except Exception as e:
                    print(f"Error processing page content: {type(e).__name__}: {e}")
                    return f"Successfully navigated to: {current_url} - {page_title}\nUnable to extract page content details."
            else:
                # Default to returning HTML for any unrecognized format
                return f"Successfully navigated to: {current_url} - {page_title}\n\nHTML content:\n{html_content}"
        except Exception as e:
            print(f"Navigation error: {type(e).__name__}: {e}")
            return f"Error navigating to {url}: {e}"
    
    @function_tool
    async def playwright_screenshot(name: str, selector: Optional[str] = None, 
                             fullPage: Optional[bool] = None,
                             width: Optional[int] = None, 
                             height: Optional[int] = None,
                             savePng: Optional[bool] = None) -> str:
        """
        Take a screenshot of the current page or a specific element.
        
        Args:
            name: Name for the screenshot
            selector: CSS selector for element to screenshot (if None, full page/viewport)
            fullPage: Store screenshot of the entire page (default: False)
            width: Width in pixels (used only without selector or fullPage)
            height: Height in pixels (used only without selector or fullPage)
            savePng: Save screenshot as PNG file (default: False)
        
        Returns:
            Base64 encoded screenshot and/or path to saved file
        """
        bc = browser_computer
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open"
        
        try:
            # Determine screenshot parameters
            full_page = fullPage if fullPage is not None else False
            dimensions = {}
            if width and height and not selector and not full_page:
                dimensions = {"width": width, "height": height}
            
            # Take the screenshot
            if selector:
                element = await bc._page.query_selector(selector)
                if not element:
                    return f"Error: Element not found with selector '{selector}'"
                png_bytes = await element.screenshot()
            else:
                png_bytes = await bc._page.screenshot(full_page=full_page, **dimensions)
            
            # Encode to base64
            base64_image = base64.b64encode(png_bytes).decode("utf-8")
            
            # Optionally save to file
            file_path = ""
            if savePng:
                file_name = f"{name}_{int(asyncio.get_event_loop().time())}.png"
                file_path = os.path.join(os.getcwd(), file_name)
                with open(file_path, "wb") as f:
                    f.write(png_bytes)
                return f"Screenshot saved to: {file_path}\nBase64: {base64_image[:50]}... (truncated)"
            
            return f"Screenshot captured. Base64: {base64_image[:50]}... (truncated)"
        except Exception as e:
            return f"Error taking screenshot: {e}"
    
    @function_tool
    async def playwright_click(selector: str) -> str:
        """
        Click an element on the page.
        
        Args:
            selector: CSS selector for the element to click. Can use:
                    - Standard CSS selectors: "#id", ".class", "tag"
                    - Attribute selectors: "[type='submit']"
                    - Text selectors: "text=Click me" (element containing this text)
        
        Returns:
            Message indicating success or failure
        """
        bc = browser_computer
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open"
        
        try:
            print(f"Attempting to click element with selector: {selector}")
            
            # Special case for text-based selection if selector doesn't look like CSS
            if selector.startswith("text=") or not any(char in selector for char in "[]().#:>+~"):
                try:
                    # Try clicking by text content directly (most reliable)
                    if selector.startswith("text="):
                        text_content = selector[5:]  # Remove 'text=' prefix
                    else:
                        text_content = selector  # Use the whole selector as text
                        
                    print(f"Interpreting as text selector: '{text_content}'")
                    
                    # Try to use locator API first (newer Playwright versions)
                    try:
                        await bc._page.get_by_text(text_content).click(timeout=5000)
                        return f"Successfully clicked element containing text: '{text_content}'"
                    except Exception as text_err:
                        print(f"Text-based click failed with get_by_text: {text_err}")
                        
                        # If that fails, try using the older text selector
                        await bc._page.click(f"text={text_content}", timeout=5000)
                        return f"Successfully clicked element containing text: '{text_content}'"
                except Exception as e:
                    print(f"Text-based click failed: {e}")
                    # Will fall back to standard selector approach
            
            # Standard selector approach (works with CSS selectors)
            try:
                # Wait for selector to be visible
                await bc._page.wait_for_selector(selector, state="visible", timeout=5000)
                # Click the element
                await bc._page.click(selector, timeout=5000)
                return f"Successfully clicked element: {selector}"
            except Exception as selector_err:
                print(f"Standard selector click failed: {selector_err}")
                
                # Try JavaScript click as a fallback
                try:
                    print("Attempting JavaScript click as fallback")
                    await bc._page.evaluate(f'''
                        (selector) => {{
                            const element = document.querySelector(selector);
                            if (element) {{
                                element.click();
                                return true;
                            }}
                            return false;
                        }}
                    ''', selector)
                    return f"Successfully clicked element using JavaScript fallback: {selector}"
                except Exception as js_err:
                    print(f"JavaScript click fallback failed: {js_err}")
                    return f"Error clicking element '{selector}': {selector_err}\nJavaScript fallback also failed: {js_err}"
                
        except Exception as e:
            print(f"Click operation failed: {e}")
            return f"Error clicking element '{selector}': {e}"
    
    @function_tool
    async def playwright_iframe_click(iframeSelector: str, selector: str) -> str:
        """
        Click an element inside an iframe.
        
        Args:
            iframeSelector: CSS selector for the iframe containing the element
            selector: CSS selector for the element to click inside the iframe
        
        Returns:
            Message indicating success or failure
        """
        bc = browser_computer
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open"
        
        try:
            # Try modern frame locator approach (newer Playwright versions)
            try:
                # Use frame locator API
                frame_locator = bc._page.frame_locator(iframeSelector)
                if frame_locator:
                    await frame_locator.locator(selector).click(timeout=5000)
                    return f"Successfully clicked element '{selector}' inside iframe '{iframeSelector}'"
            except Exception as frame_locator_err:
                print(f"Frame locator approach failed: {frame_locator_err}")
                # Fall back to older approach
            
            # Find the iframe (legacy approach)
            iframe = await bc._page.wait_for_selector(iframeSelector, timeout=5000)
            if not iframe:
                return f"Error: Iframe not found with selector '{iframeSelector}'"
            
            # Get the iframe content
            frame = await iframe.content_frame()
            if not frame:
                return f"Error: Could not access content frame of iframe '{iframeSelector}'"
            
            # Click the element inside the iframe
            await frame.click(selector, timeout=5000)
            return f"Successfully clicked element '{selector}' inside iframe '{iframeSelector}'"
        except Exception as e:
            return f"Error clicking element in iframe: {e}"
    
    @function_tool
    async def playwright_fill(selector: str, value: str) -> str:
        """
        Fill out an input field.
        
        Args:
            selector: CSS selector for the input field
            value: Value to fill in the field
        
        Returns:
            Message indicating success or failure
        """
        bc = browser_computer
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open"
        
        try:
            # Wait for selector to be visible
            await bc._page.wait_for_selector(selector, state="visible", timeout=5000)
            # Fill the field
            await bc._page.fill(selector, value)
            return f"Successfully filled '{value}' into field: {selector}"
        except Exception as e:
            return f"Error filling field '{selector}': {e}"
    
    @function_tool
    async def playwright_select(selector: str, value: str) -> str:
        """
        Select an option from a dropdown.
        
        Args:
            selector: CSS selector for the select element
            value: Value to select
        
        Returns:
            Message indicating success or failure
        """
        bc = browser_computer
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open"
        
        try:
            # Wait for selector to be visible
            await bc._page.wait_for_selector(selector, state="visible", timeout=5000)
            # Select the option
            await bc._page.select_option(selector, value=value)
            return f"Successfully selected value '{value}' in dropdown: {selector}"
        except Exception as e:
            return f"Error selecting option in dropdown '{selector}': {e}"
    
    @function_tool
    async def playwright_hover(selector: str) -> str:
        """
        Hover over an element on the page.
        
        Args:
            selector: CSS selector for the element to hover over
        
        Returns:
            Message indicating success or failure
        """
        bc = browser_computer
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open"
        
        try:
            # Wait for selector to be visible
            await bc._page.wait_for_selector(selector, state="visible", timeout=5000)
            # Hover over the element
            await bc._page.hover(selector)
            return f"Successfully hovered over element: {selector}"
        except Exception as e:
            return f"Error hovering over element '{selector}': {e}"
    
    @function_tool
    async def playwright_evaluate(script: str) -> str:
        """
        Execute JavaScript in the browser console.
        
        Args:
            script: JavaScript code to execute
        
        Returns:
            Result of the JavaScript execution
        """
        bc = browser_computer
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open"
        
        try:
            print(f"Executing script: {script}")
            
            # Execute script using a reliable approach with addScriptTag
            try:
                # Create a unique global variable to store the result
                result_var = f"__playwright_result_{int(asyncio.get_event_loop().time() * 1000)}"
                
                # Prepare a script that assigns the result to our global variable
                wrapped_script = f"""
                try {{
                    window.{result_var} = (function() {{
                        {script}
                    }})();
                }} catch (e) {{
                    window.{result_var} = {{ error: e.toString() }};
                }}
                """
                
                # Add the script to the page
                await bc._page.add_script_tag(content=wrapped_script)
                
                # Retrieve the result from the global variable
                # Handle both property and method versions of evaluate
                evaluate_method = bc._page.evaluate
                if callable(evaluate_method):
                    js_result = await evaluate_method(f"() => window.{result_var}")
                else:
                    # For newer Playwright versions, handle as property
                    js_result = await bc._page.evaluate(f"() => window.{result_var}")
                
                # Clean up the global variable
                try:
                    # Handle both property and method versions of evaluate
                    if callable(evaluate_method):
                        await evaluate_method(f"() => {{ delete window.{result_var}; }}")
                    else:
                        # For newer Playwright versions, handle as property
                        await bc._page.evaluate(f"() => {{ delete window.{result_var}; }}")
                except Exception as cleanup_err:
                    print(f"Error cleaning up script variable: {cleanup_err}")
                    # Non-critical error, continue execution
                
                # Check if we got an error
                if isinstance(js_result, dict) and 'error' in js_result:
                    return f"JavaScript error: {js_result['error']}"
                
                # Format the result for readability
                if js_result is None:
                    return "Script executed successfully (no return value)"
                
                if isinstance(js_result, (dict, list)):
                    import json
                    return f"Script result:\n{json.dumps(js_result, indent=2)}"
                
                return f"Script result: {js_result}"
            except Exception as e:
                print(f"Script execution error: {type(e).__name__}: {e}")
                
                # Try another approach - this time with just a simple eval
                try:
                    # For simple statements, try direct evaluation
                    if "return" not in script and ";" not in script and len(script.strip().split("\n")) == 1:
                        # Handle both property and method versions of evaluate
                        evaluate_method = bc._page.evaluate
                        if callable(evaluate_method):
                            simple_result = await evaluate_method(f"() => {{{script}}}")
                        else:
                            # For newer Playwright versions
                            simple_result = await bc._page.evaluate(f"() => {{{script}}}")
                            
                        return f"Script result: {simple_result}"
                except Exception as e2:
                    print(f"Simple evaluation error: {type(e2).__name__}: {e2}")
                
                # Final fallback - try executing without returning a result
                try:
                    # Create another script tag as the most basic approach
                    final_script = f"""
                    try {{
                        {script}
                    }} catch (e) {{
                        console.error("Script execution error:", e);
                    }}
                    """
                    await bc._page.add_script_tag(content=final_script)
                    return "Script executed successfully (result unavailable)"
                except Exception as e3:
                    print(f"Fallback execution error: {type(e3).__name__}: {e3}")
                    return f"Error executing script: {e}"
                    
        except Exception as e:
            print(f"General script execution error: {type(e).__name__}: {e}")
            return f"Error executing script: {e}"

    @function_tool
    async def playwright_close() -> str:
        """
        Close the browser.
        
        Returns:
            Message indicating success or failure
        """
        bc = browser_computer
        if not bc._browser:
            return "Browser is already closed or not initialized"
        
        try:
            await bc._browser.close()
            if bc._playwright:
                await bc._playwright.stop()
            return "Browser closed successfully"
        except Exception as e:
            return f"Error closing browser: {e}"
            
    # HTTP request helper function
    async def _make_http_request(browser_computer, method: str, url: str, data: Any = None) -> str:
        """
        Helper function to make HTTP requests with consistent error handling.
        
        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            url: URL to make the request to
            data: Optional data for request body
            
        Returns:
            Formatted response from the server
        """
        if not browser_computer._page:
            return "Error: Browser is not initialized or no page is currently open"
            
        try:
            # Use Playwright's API request context
            context = await browser_computer._browser.new_context()
            
            try:
                # Execute the right HTTP method
                request_method = getattr(context.request, method.lower())
                
                # Call with or without data parameter as appropriate
                if method in ['POST', 'PUT', 'PATCH'] and data is not None:
                    response = await request_method(url, data=data)
                else:
                    response = await request_method(url)
                
                # Handle both property and method versions of status
                status = response.status
                if callable(status):
                    status = await status()
                
                # Try to parse as JSON first
                try:
                    # Handle both property and method versions of json
                    json_method = response.json
                    if callable(json_method):
                        result = await json_method()
                    else:
                        # If it's a property, assume it's already the result
                        result = json_method
                    
                    import json
                    return f"{method} {url} - Status: {status}\nResponse:\n{json.dumps(result, indent=2)}"
                except:
                    # Fall back to text
                    # Handle both property and method versions of text
                    text_method = response.text
                    if callable(text_method):
                        result = await text_method()
                    else:
                        # If it's a property, assume it's already the result
                        result = text_method
                        
                    return f"{method} {url} - Status: {status}\nResponse:\n{result}"
            finally:
                # Make sure to close the context
                await context.close()
        except Exception as e:
            return f"Error executing {method} request: {e}"
    
    # HTTP API tools
    @function_tool
    async def playwright_get(url: str) -> str:
        """
        Perform an HTTP GET request.
        
        Args:
            url: URL to perform GET operation
        
        Returns:
            Response from the server
        """
        return await _make_http_request(browser_computer, "GET", url)
            
    # Helper function to parse JSON data for HTTP requests
    def _parse_json_data(value: str) -> Any:
        """Parse JSON string if possible, otherwise return as is"""
        data = value
        try:
            import json
            data = json.loads(value)
        except:
            # If not JSON, use as raw string
            pass
        return data
        
    @function_tool
    async def playwright_post(url: str, value: str) -> str:
        """
        Perform an HTTP POST request.
        
        Args:
            url: URL to perform POST operation
            value: Data to post in the body (JSON string)
            
        Returns:
            Response from the server
        """
        data = _parse_json_data(value)
        return await _make_http_request(browser_computer, "POST", url, data)
            
    @function_tool
    async def playwright_put(url: str, value: str) -> str:
        """
        Perform an HTTP PUT request.
        
        Args:
            url: URL to perform PUT operation
            value: Data to put in the body (JSON string)
            
        Returns:
            Response from the server
        """
        data = _parse_json_data(value)
        return await _make_http_request(browser_computer, "PUT", url, data)
            
    @function_tool
    async def playwright_patch(url: str, value: str) -> str:
        """
        Perform an HTTP PATCH request.
        
        Args:
            url: URL to perform PATCH operation
            value: Data to patch in the body (JSON string)
            
        Returns:
            Response from the server
        """
        data = _parse_json_data(value)
        return await _make_http_request(browser_computer, "PATCH", url, data)
            
    @function_tool
    async def playwright_delete(url: str) -> str:
        """
        Perform an HTTP DELETE request.
        
        Args:
            url: URL to perform DELETE operation
            
        Returns:
            Response from the server
        """
        return await _make_http_request(browser_computer, "DELETE", url)
    
    # No legacy navigate function - functionality merged into playwright_navigate
    
    @function_tool
    async def playwright_get_elements(selectors: Optional[str] = None) -> str:
        """
        Get a list of interactive elements on the page to help with selecting elements.
        
        Args:
            selectors: Optional CSS selectors to search for (default: common interactive elements)
        
        Returns:
            A list of element details including tag, ID, class, and text content
        """
        bc = browser_computer
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open"
        
        try:
            print("Finding elements on page")
            
            # Default to common interactive elements if no selectors provided
            element_selectors = selectors if selectors else "button, a, input, select, textarea, [role='button']"
            
            # Get elements with their key properties
            # Use proper parameterized evaluate to avoid string interpolation issues
            elements = await bc._page.evaluate(
                """(selectors) => {
                    const elements = document.querySelectorAll(selectors);
                    return Array.from(elements).map(el => {
                        // Get computed styles to check visibility
                        const style = window.getComputedStyle(el);
                        const isVisible = style.display !== 'none' && 
                                        style.visibility !== 'hidden' && 
                                        style.opacity !== '0';
                        
                        // Get element position if visible
                        let rect = null;
                        if (isVisible) {
                            const boundingRect = el.getBoundingClientRect();
                            if (boundingRect && boundingRect.width > 0 && boundingRect.height > 0) {
                                rect = {
                                    x: boundingRect.x || 0,
                                    y: boundingRect.y || 0,
                                    width: boundingRect.width || 0,
                                    height: boundingRect.height || 0
                                };
                            }
                        }
                        
                        // Safely access element properties
                        const getAttrSafe = (element, attr) => {
                            try {
                                return element[attr] || null;
                            } catch (e) {
                                return null;
                            }
                        };
                        
                        // Safely get text content
                        const getTextSafe = (element) => {
                            try {
                                return element.textContent ? 
                                    element.textContent.trim().substring(0, 100) : null;
                            } catch (e) {
                                return null;
                            }
                        };
                        
                        // Safely get attributes
                        const getAttributesSafe = (element) => {
                            try {
                                if (!element.attributes) return '';
                                return Array.from(element.attributes)
                                    .filter(attr => attr && attr.name && !['id', 'class', 'style'].includes(attr.name))
                                    .map(attr => `${attr.name}="${attr.value || ''}"`)
                                    .join(' ');
                            } catch (e) {
                                return '';
                            }
                        };
                        
                        // Return element details with safe property access
                        return {
                            tag: el.tagName ? el.tagName.toLowerCase() : 'unknown',
                            id: getAttrSafe(el, 'id'),
                            classes: getAttrSafe(el, 'className'),
                            type: getAttrSafe(el, 'type'),
                            name: getAttrSafe(el, 'name'),
                            value: getAttrSafe(el, 'value'),
                            text: getTextSafe(el),
                            isVisible: isVisible && rect !== null,
                            href: getAttrSafe(el, 'href'),
                            position: rect,
                            attributes: getAttributesSafe(el)
                        };
                    });
                }""", 
                element_selectors
            )
            
            # Filter out empty or invisible elements and generate selectors
            visible_elements = [el for el in elements if el.get('isVisible', False)]
            
            # Format the results in a human-readable way
            results = ["# Interactive Elements Found on Page", ""]
            
            if not visible_elements:
                results.append("No visible interactive elements found with selector: " + element_selectors)
            else:
                results.append(f"Found {len(visible_elements)} visible interactive elements:")
                
                for i, el in enumerate(visible_elements, 1):
                    # Generate useful selectors for this element
                    selectors = []
                    
                    if el.get('id'):
                        selectors.append(f"#{el.get('id')}")
                        
                    if el.get('text') and len(el.get('text').strip()) > 0 and len(el.get('text').strip()) < 50:
                        selectors.append(f"text={el.get('text').strip()}")
                    
                    if el.get('tag') == 'a' and el.get('href'):
                        selectors.append(f"a[href='{el.get('href').split('?')[0]}']")
                        
                    if el.get('tag') == 'button' or el.get('type') == 'submit':
                        selectors.append(f"{el.get('tag')}[type='{el.get('type')}']")
                    
                    # Format element details
                    line = f"## {i}. {el.get('tag', 'unknown')}"
                    if el.get('type'):
                        line += f" (type={el.get('type')})"
                    results.append(line)
                    
                    if el.get('text'):
                        results.append(f"   Text: \"{el.get('text')}\"")
                        
                    if selectors:
                        results.append(f"   Selectors to use:")
                        for selector in selectors:
                            results.append(f"   - `{selector}`")
                            
                    results.append("")  # Add a blank line between elements
            
            return "\n".join(results)
        except Exception as e:
            print(f"Error getting page elements: {e}")
            return f"Error getting page elements: {e}"
    
    @function_tool
    async def playwright_get_text(selector: Optional[str] = None, 
                           includeHtml: Optional[bool] = None,
                           maxLength: Optional[int] = None) -> str:
        """
        Get text content from the current page or a specific element with advanced options.
        
        Args:
            selector: Optional CSS selector for a specific element
            includeHtml: Whether to include HTML structure info (default: False)
            maxLength: Maximum content length to return (default: 5000)
            
        Returns:
            The text content from the current page or element
        """
        bc = browser_computer
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open"
        
        # Set defaults
        include_html = includeHtml if includeHtml is not None else False
        max_length = maxLength if maxLength is not None else 5000
        
        try:
            print(f"Getting text content. Selector: {selector if selector else 'entire page'}")
            
            # Get page content using content() method
            html = await bc._page.content()
            
            # Get current URL - handle both property and method versions
            try:
                url_value = bc._page.url
                if callable(url_value):
                    current_url = await url_value()
                else:
                    current_url = url_value
            except Exception as url_err:
                print(f"Error getting URL: {url_err}")
                current_url = "Unknown URL"
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Get page title
            page_title = soup.title.string if soup.title else "No title"
            
            # If selector is provided, get content from that element
            if selector:
                # Find element in the soup
                element = soup.select_one(selector)
                if not element:
                    return f"Error: Element not found with selector '{selector}'"
                
                # Clean up the element
                for script in element.find_all(['script', 'style']):
                    script.decompose()
                
                # Get content from the element
                if include_html:
                    content = str(element)
                else:
                    text_content = element.get_text(separator='\n', strip=True)
                    # Clean up the text
                    lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                    content = '\n'.join(lines)
            else:
                # Get content from whole page, focusing on main content
                
                # Try to identify main content containers
                main_content = None
                
                # Look for common content containers
                for container in ['main', 'article', '#content', '.content', '#main', '.main']:
                    elements = soup.select(container)
                    if elements:
                        main_content = elements[0]
                        print(f"Found main content container: {container}")
                        break
                
                # If no main content container found, use body
                if not main_content:
                    main_content = soup.body if soup.body else soup
                
                # Clean up the content
                for script in main_content.find_all(['script', 'style']):
                    script.decompose()
                
                # Get content
                if include_html:
                    content = str(main_content)
                else:
                    text_content = main_content.get_text(separator='\n', strip=True)
                    # Clean up the text
                    lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                    content = '\n'.join(lines)
            
            # Truncate if too long
            if len(content) > max_length:
                truncated_content = content[:max_length] + f"\n\n[Content truncated. Total length: {len(content)} characters]"
            else:
                truncated_content = content
            
            return f"Page: {page_title}\nURL: {current_url}\n\nContent:\n{truncated_content}"
        except Exception as e:
            print(f"Error getting text content: {type(e).__name__}: {e}")
            return f"Error getting text content: {e}"
    
    @function_tool
    async def playwright_get_location(api_key: Optional[str] = None,
                               service: Optional[str] = None,
                               include_details: Optional[bool] = None,
                               timeout: Optional[int] = None,
                               use_cache: Optional[bool] = None,
                               fallback_service: Optional[str] = None,
                               language: Optional[str] = None) -> str:
        """
        Get the current geolocation information with enhanced details and error handling.
        
        Args:
            api_key: Optional API key for services that require authentication
            service: Geolocation service to use ('ipinfo', 'ipapi', 'geojs', 'ipgeolocation')
            include_details: Whether to include detailed location data (region, city, timezone, etc.)
            timeout: Request timeout in milliseconds (default: 5000)
            use_cache: Whether to use cached location data if available (default: True)
            fallback_service: Secondary service to try if primary service fails
            language: Preferred language for location names (ISO 639-1 code)
            
        Returns:
            JSON string containing location information or error details
        """
        bc = browser_computer
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open"
            
        # Default values
        location_service = service or "ipinfo"
        details = include_details if include_details is not None else True
        request_timeout = timeout or 5000
        use_location_cache = use_cache if use_cache is not None else True
        locale = language or "en"
        
        # Define cache key for this specific request
        cache_key = f"location_cache_{location_service}_{details}_{locale}"
        
        # Check if we have a cached result
        if use_location_cache:
            try:
                cache_result = await bc._page.evaluate(f"() => window.{cache_key}")
                if cache_result:
                    print(f"Using cached location data from {location_service}")
                    return f"Location from cache ({location_service}):\n{cache_result}"
            except Exception as cache_err:
                print(f"Cache retrieval error: {cache_err}")
                # Continue with fresh request
        
        # Define API endpoints and parameters for different services
        service_configs = {
            "ipinfo": {
                "url": f"https://ipinfo.io/json{f'?token={api_key}' if api_key else ''}",
                "extract": """
                    response => {
                        return {
                            ip: response.ip,
                            city: response.city,
                            region: response.region,
                            country: response.country,
                            country_name: response.country_name || response.country,
                            loc: response.loc,
                            postal: response.postal,
                            timezone: response.timezone,
                            asn: response.org,
                            hostname: response.hostname
                        };
                    }
                """
            },
            "ipapi": {
                "url": "https://ipapi.co/json/",
                "extract": """
                    response => {
                        return {
                            ip: response.ip,
                            city: response.city,
                            region: response.region,
                            region_code: response.region_code,
                            country: response.country_code,
                            country_name: response.country_name,
                            continent_code: response.continent_code,
                            postal: response.postal,
                            latitude: response.latitude,
                            longitude: response.longitude,
                            timezone: response.timezone,
                            utc_offset: response.utc_offset,
                            currency: response.currency,
                            currency_name: response.currency_name,
                            languages: response.languages,
                            asn: response.asn,
                            org: response.org
                        };
                    }
                """
            },
            "geojs": {
                "url": "https://get.geojs.io/v1/ip/geo.json",
                "extract": """
                    response => {
                        return {
                            ip: response.ip,
                            country: response.country_code,
                            country_name: response.country,
                            region: response.region,
                            city: response.city,
                            latitude: response.latitude,
                            longitude: response.longitude,
                            timezone: response.timezone,
                            organization: response.organization
                        };
                    }
                """
            },
            "ipgeolocation": {
                "url": f"https://api.ipgeolocation.io/ipgeo?apiKey={api_key or ''}&lang={locale}",
                "extract": """
                    response => {
                        return {
                            ip: response.ip,
                            continent_code: response.continent_code,
                            continent_name: response.continent_name,
                            country: response.country_code2,
                            country_name: response.country_name,
                            region: response.state_prov,
                            city: response.city,
                            district: response.district,
                            zipcode: response.zipcode,
                            latitude: response.latitude,
                            longitude: response.longitude,
                            timezone: response.time_zone ? response.time_zone.name : null,
                            timezone_offset: response.time_zone ? response.time_zone.offset : null,
                            currency: response.currency ? response.currency.code : null,
                            currency_name: response.currency ? response.currency.name : null,
                            isp: response.isp,
                            connection_type: response.connection_type,
                            organization: response.organization
                        };
                    }
                """
            }
        }
        
        # Error classes for better error handling
        error_classes = """
        class GeolocationError extends Error {
            constructor(message, category, service) {
                super(message);
                this.name = "GeolocationError";
                this.category = category;
                this.service = service;
            }
        }
        
        class NetworkError extends GeolocationError {
            constructor(message, service) {
                super(message, "NETWORK", service);
                this.name = "NetworkError";
            }
        }
        
        class TimeoutError extends GeolocationError {
            constructor(message, service) {
                super(message, "TIMEOUT", service);
                this.name = "TimeoutError";
            }
        }
        
        class ServiceError extends GeolocationError {
            constructor(message, service) {
                super(message, "SERVICE", service);
                this.name = "ServiceError";
            }
        }
        
        class ParseError extends GeolocationError {
            constructor(message, service) {
                super(message, "PARSE", service);
                this.name = "ParseError";
            }
        }
        """
        
        # Main fetch function with error handling
        fetch_script = f"""
        {error_classes}
        
        async function fetchLocation(service, config, timeout) {{
            try {{
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), timeout);
                
                try {{
                    const response = await fetch(config.url, {{ 
                        signal: controller.signal,
                        headers: {{ 'Accept': 'application/json' }}
                    }});
                    
                    clearTimeout(timeoutId);
                    
                    if (!response.ok) {{
                        throw new ServiceError(`Service returned status ${{response.status}}: ${{response.statusText}}`, service);
                    }}
                    
                    const data = await response.json();
                    const result = ({config.extract})(data);
                    
                    // Add metadata
                    result.source = service;
                    result.timestamp = new Date().toISOString();
                    
                    // Save to cache
                    window.{cache_key} = JSON.stringify(result);
                    
                    return result;
                }} catch (e) {{
                    clearTimeout(timeoutId);
                    
                    if (e.name === 'AbortError') {{
                        throw new TimeoutError(`Request to ${{service}} timed out after ${{timeout}}ms`, service);
                    }} else if (e.name === 'ServiceError') {{
                        throw e;
                    }} else {{
                        throw new NetworkError(`Network error fetching from ${{service}}: ${{e.message}}`, service);
                    }}
                }}
            }} catch (e) {{
                // Return a standardized error object
                return {{
                    error: true,
                    service: service,
                    errorType: e.name,
                    errorCategory: e.category || 'UNKNOWN',
                    message: e.message,
                    timestamp: new Date().toISOString()
                }};
            }}
        }}
        
        async function getLocation() {{
            let service = '{location_service}';
            let config = {{}};
            
            // Primary service configuration
            switch(service) {{
                case 'ipinfo':
                    config = {service_configs['ipinfo']};
                    break;
                case 'ipapi':
                    config = {service_configs['ipapi']};
                    break;
                case 'geojs':
                    config = {service_configs['geojs']};
                    break;
                case 'ipgeolocation':
                    config = {service_configs['ipgeolocation']};
                    break;
                default:
                    config = {service_configs['ipinfo']};
                    service = 'ipinfo';
            }}
            
            // Primary request
            const result = await fetchLocation(service, config, {request_timeout});
            
            // Check if we got an error
            if (result.error) {{
                // Try fallback service if specified
                const fallback = '{fallback_service}';
                if (fallback && fallback !== service) {{
                    let fallbackConfig = {{}};
                    
                    switch(fallback) {{
                        case 'ipinfo':
                            fallbackConfig = {service_configs['ipinfo']};
                            break;
                        case 'ipapi':
                            fallbackConfig = {service_configs['ipapi']};
                            break;
                        case 'geojs':
                            fallbackConfig = {service_configs['geojs']};
                            break;
                        case 'ipgeolocation':
                            fallbackConfig = {service_configs['ipgeolocation']};
                            break;
                    }}
                    
                    console.log(`Primary service ${{service}} failed, trying fallback ${{fallback}}`);
                    const fallbackResult = await fetchLocation(fallback, fallbackConfig, {request_timeout});
                    
                    // Return fallback result (could be success or also error)
                    if (!fallbackResult.error) {{
                        fallbackResult.fallback = true;
                        fallbackResult.primary_error = result;
                    }}
                    return fallbackResult;
                }}
                
                return result;
            }}
            
            return result;
        }}
        
        return getLocation();
        """
        
        try:
            # Execute the script
            print(f"Fetching location using service: {location_service}")
            location_data = await bc._page.evaluate(fetch_script)
            
            # Format the response based on error state and requested detail level
            if location_data.get('error', False):
                error_type = location_data.get('errorType', 'Unknown')
                error_message = location_data.get('message', 'Unknown error')
                service_name = location_data.get('service', location_service)
                
                return f"Error getting location from {service_name}: {error_type} - {error_message}"
            else:
                # Format successful response
                import json
                
                # Check if this is a fallback result
                if location_data.get('fallback', False):
                    primary_error = location_data.get('primary_error', {})
                    primary_service = primary_error.get('service', location_service)
                    primary_error_message = primary_error.get('message', 'Unknown error')
                    
                    fallback_notice = f"Primary service ({primary_service}) failed: {primary_error_message}. Using fallback service ({location_data.get('source')})."
                else:
                    fallback_notice = ""
                
                # Filter details if requested
                if not details:
                    # Basic location info
                    basic_info = {
                        'ip': location_data.get('ip'),
                        'country': location_data.get('country'),
                        'country_name': location_data.get('country_name')
                    }
                    
                    response_text = json.dumps(basic_info, indent=2)
                else:
                    # Full details
                    response_text = json.dumps(location_data, indent=2)
                
                # Add fallback notice if applicable
                if fallback_notice:
                    return f"{fallback_notice}\n\nLocation:\n{response_text}"
                else:
                    return f"Location from {location_data.get('source')}:\n{response_text}"
                
        except Exception as e:
            print(f"Error executing geolocation script: {type(e).__name__}: {e}")
            return f"Error getting location: {e}"

    @function_tool
    async def playwright_keypress(key: str, selector: Optional[str] = None) -> str:
        """
        Press a key or key combination on the page or in a specific element.
        
        Args:
            key: Key or key combination to press (e.g., "Enter", "Control+a", "ArrowDown")
            selector: Optional CSS selector to focus before pressing key
            
        Returns:
            Message indicating success or failure
        """
        bc = browser_computer
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open"
        
        try:
            # Convert common key names to Playwright format
            normalized_key = key.lower()
            if normalized_key in CUA_KEY_TO_PLAYWRIGHT_KEY:
                key = CUA_KEY_TO_PLAYWRIGHT_KEY[normalized_key]
            
            # If a selector is provided, focus that element first
            if selector:
                print(f"Focusing element {selector} before pressing {key}")
                await bc._page.focus(selector)
            
            # Handle key combinations (e.g., "Control+a")
            if "+" in key:
                key_parts = key.split("+")
                modifiers = key_parts[:-1]
                key_to_press = key_parts[-1]
                
                # Convert modifiers to Playwright format
                playwright_modifiers = []
                for modifier in modifiers:
                    modifier_lower = modifier.lower()
                    if modifier_lower in CUA_KEY_TO_PLAYWRIGHT_KEY:
                        playwright_modifiers.append(CUA_KEY_TO_PLAYWRIGHT_KEY[modifier_lower])
                    else:
                        playwright_modifiers.append(modifier)
                
                # Convert key to Playwright format if needed
                if key_to_press.lower() in CUA_KEY_TO_PLAYWRIGHT_KEY:
                    key_to_press = CUA_KEY_TO_PLAYWRIGHT_KEY[key_to_press.lower()]
                
                print(f"Pressing key combination: modifiers={playwright_modifiers}, key={key_to_press}")
                await bc._page.keyboard.press(key_to_press, modifiers=playwright_modifiers)
            else:
                print(f"Pressing key: {key}")
                await bc._page.keyboard.press(key)
                
            return f"Successfully pressed {key}" + (f" on element {selector}" if selector else "")
        except Exception as e:
            print(f"Error pressing key {key}: {e}")
            return f"Error pressing key {key}: {e}"
            
    # Return all tools as a dictionary
    return {
        "playwright_navigate": playwright_navigate,
        "playwright_screenshot": playwright_screenshot,
        "playwright_click": playwright_click,
        "playwright_iframe_click": playwright_iframe_click,
        "playwright_fill": playwright_fill,
        "playwright_select": playwright_select,
        "playwright_hover": playwright_hover,
        "playwright_evaluate": playwright_evaluate,
        "playwright_get_text": playwright_get_text,
        "playwright_get_elements": playwright_get_elements,
        "playwright_close": playwright_close,
        "playwright_get": playwright_get,
        "playwright_post": playwright_post,
        "playwright_put": playwright_put,
        "playwright_patch": playwright_patch,
        "playwright_delete": playwright_delete,
        "playwright_get_location": playwright_get_location,
        "playwright_keypress": playwright_keypress
    }