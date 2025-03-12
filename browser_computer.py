"""
Browser computer implementation using Playwright.
Provides browser automation capabilities for agents to interact with web pages.
"""

import asyncio
import base64
from typing import Literal, Union

from playwright.async_api import Browser, Page, Playwright, async_playwright

from agents import AsyncComputer, Button, Environment

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
    """A computer implementation using a local Playwright browser."""

    def __init__(self, headless=False, browser_type="chromium", start_url="about:blank"):
        """
        Initialize the browser computer.
        
        Args:
            headless: Whether to run the browser in headless mode
            browser_type: Type of browser to use (chromium, firefox, webkit)
            start_url: Initial URL to navigate to when starting the browser
        """
        self._playwright: Union[Playwright, None] = None
        self._browser: Union[Browser, None] = None
        self._page: Union[Page, None] = None
        self._headless = headless
        self._browser_type = browser_type
        self._start_url = start_url

    async def _get_browser_and_page(self) -> tuple[Browser, Page]:
        """Launch browser and create a new page with specified dimensions."""
        width, height = self.dimensions
        launch_args = [f"--window-size={width},{height}"]
        
        # Launch the appropriate browser type
        if self._browser_type == "chromium":
            browser = await self.playwright.chromium.launch(
                headless=self._headless, 
                args=launch_args
            )
        elif self._browser_type == "firefox":
            browser = await self.playwright.firefox.launch(
                headless=self._headless, 
                args=launch_args
            )
        elif self._browser_type == "webkit":
            browser = await self.playwright.webkit.launch(
                headless=self._headless, 
                args=launch_args
            )
        else:
            # Default to chromium
            browser = await self.playwright.chromium.launch(
                headless=self._headless, 
                args=launch_args
            )
        
        # Create a new page and navigate to the start URL
        page = await browser.new_page()
        await page.set_viewport_size({"width": width, "height": height})
        await page.goto(self._start_url)
        return browser, page

    async def __aenter__(self):
        """Start Playwright when entering the context."""
        self._playwright = await async_playwright().start()
        self._browser, self._page = await self._get_browser_and_page()
        return self
        
    async def navigate(self, url: str) -> None:
        """Navigate to a specific URL."""
        await self.page.goto(url)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close browser and stop Playwright when exiting the context."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @property
    def playwright(self) -> Playwright:
        """Get the Playwright instance."""
        assert self._playwright is not None, "Playwright instance not initialized"
        return self._playwright

    @property
    def browser(self) -> Browser:
        """Get the browser instance."""
        assert self._browser is not None, "Browser not initialized"
        return self._browser

    @property
    def page(self) -> Page:
        """Get the current page."""
        assert self._page is not None, "Page not initialized"
        return self._page

    @property
    def environment(self) -> Environment:
        """Get the environment type."""
        return "browser"

    @property
    def dimensions(self) -> tuple[int, int]:
        """Get the browser dimensions."""
        return (1280, 800)

    async def screenshot(self) -> str:
        """Capture screenshot of the current page (viewport only)."""
        png_bytes = await self.page.screenshot(full_page=False)
        return base64.b64encode(png_bytes).decode("utf-8")

    async def click(self, x: int, y: int, button: Button = "left") -> None:
        """Click at the specified position with the specified button."""
        playwright_button: Literal["left", "middle", "right"] = "left"

        # Playwright only supports left, middle, right buttons
        if button in ("left", "right", "middle"):
            playwright_button = button  # type: ignore

        await self.page.mouse.click(x, y, button=playwright_button)

    async def double_click(self, x: int, y: int) -> None:
        """Double-click at the specified position."""
        await self.page.mouse.dblclick(x, y)

    async def scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        """Scroll the page at the specified position by the specified amount."""
        await self.page.mouse.move(x, y)
        await self.page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y})")

    async def type(self, text: str) -> None:
        """Type the specified text."""
        await self.page.keyboard.type(text)

    async def wait(self) -> None:
        """Wait for a short period."""
        await asyncio.sleep(1)

    async def move(self, x: int, y: int) -> None:
        """Move the mouse to the specified position."""
        await self.page.mouse.move(x, y)

    async def keypress(self, keys: list[str]) -> None:
        """Press the specified keys."""
        for key in keys:
            mapped_key = CUA_KEY_TO_PLAYWRIGHT_KEY.get(key.lower(), key)
            await self.page.keyboard.press(mapped_key)

    async def drag(self, path: list[tuple[int, int]]) -> None:
        """Drag the mouse along the specified path."""
        if not path:
            return
        await self.page.mouse.move(path[0][0], path[0][1])
        await self.page.mouse.down()
        for px, py in path[1:]:
            await self.page.mouse.move(px, py)
        await self.page.mouse.up()