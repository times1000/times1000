"""
Browser computer implementation using Playwright.
Provides browser automation capabilities for agents to interact with web pages.
"""

import asyncio
import base64
from typing import Literal, Optional, Union, List, Dict

from playwright.async_api import async_playwright, Browser, Page, Playwright
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

    def __init__(self, headless: bool = False):
        """Initialize the Playwright computer."""
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self.headless = headless

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
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the browser when exiting the context."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

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
            await self._page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y})")
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


# Create a navigation tool function using the function_tool decorator
def create_navigate_tool(browser_computer):
    """Create a navigation tool for the browser"""
    
    @function_tool
    async def navigate(url: str, return_content: Optional[bool] = None, format: Optional[str] = None) -> str:
        """
        Navigate the browser to a specific URL and optionally return page content.
        
        Args:
            url: The URL to navigate to (should start with http:// or https://)
            return_content: Whether to return the page content (True or False)
            format: The format to return content in - "text", "html", or "markdown"
        
        Returns:
            A message indicating successful navigation and optionally the page content
        """
        if not url:
            return "Error: URL parameter is required"
        
        # Ensure URL has a protocol
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        # Navigate to the URL
        await browser_computer.goto(url)
        
        # Base success message
        message = f"Successfully navigated to {url}. I can now interact with elements on this page using the ComputerTool."
        
        # Set defaults if None
        if return_content is None:
            return_content = False
        if format is None:
            format = "text"
            
        # Optionally get and return the page content
        if return_content:
            content_message = await get_page_content(format)
            return message + "\n\n" + content_message
        
        return message
    
    @function_tool
    async def get_page_content(format: Optional[str] = None) -> str:
        """
        Get content from the current page without navigating to a new URL.
        
        Args:
            format: The format to return content in - "text", "html", or "markdown"
        
        Returns:
            The page content in the requested format
        """
        # Use the outer browser_computer
        bc = browser_computer
        
        # Set default format if None
        if format is None:
            format = "text"
            
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open."
        
        try:
            # Get the current URL for reference
            current_url = await bc._page.url()
            
            if format.lower() == "html":
                content = await bc._page.content()
                return f"Page HTML content from {current_url}:\n{content}"
            elif format.lower() == "markdown":
                # Get the HTML content for conversion to markdown
                html_content = await bc._page.content()
                
                # Get the title
                title = await bc._page.title()
                title_md = f"# {title}\n\n" if title else ""
                
                # Define a synchronous function for the conversion
                def convert_html_to_markdown(html):
                    # Use BeautifulSoup to find the main content
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Try to get the main content area
                    main_content = soup.find('article') or soup.find('main') or soup.find('body')
                    
                    # Convert to markdown with improved settings
                    md_content = markdownify(str(main_content), heading_style="ATX")
                    
                    # Clean up the markdown output
                    md_content = re.sub(r'\n{3,}', '\n\n', md_content)  # Remove excessive newlines
                    
                    return md_content
                
                # Run the conversion in a separate thread to avoid blocking
                md_content = await asyncio.to_thread(convert_html_to_markdown, html_content)
                content = title_md + md_content
                
                return f"Page content (Markdown) from {current_url}:\n{content}"
            else:  # Default to text
                content = await bc._page.evaluate('() => document.body.innerText')
                return f"Page text content from {current_url}:\n{content}"
        except Exception as e:
            return f"Error retrieving page content: {e}"
    
    return navigate, get_page_content