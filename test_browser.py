#!/usr/bin/env python
"""
Test script to verify browser initialization and navigation
"""

import asyncio
import sys
from utils.browser_computer import LocalPlaywrightComputer, create_browser_tools

async def test_browser():
    print("Testing browser initialization...")
    try:
        computer = await LocalPlaywrightComputer(headless=False, silent=False).__aenter__()
        print("Browser initialized successfully!")
        print(f"Browser computer has _page: {hasattr(computer, '_page')}")
        print(f"Browser computer has _browser: {hasattr(computer, '_browser')}")
        
        # Test create_browser_tools
        print("\nTesting browser tools creation...")
        tools = create_browser_tools(computer)
        print(f"Created {len(tools)} browser tools")
        
        # Test navigation
        if 'playwright_navigate' in tools:
            navigate_tool = tools['playwright_navigate']
            print("\nTesting navigation...")
            
            result = await navigate_tool.call(url="https://example.com")
            print("Navigation result:", result[:100] + "..." if len(result) > 100 else result)
        
        # Clean up
        print("\nCleaning up browser...")
        await computer.__aexit__(None, None, None)
        print("Browser cleaned up successfully!")
        
        return True
    except Exception as e:
        print(f"Error during test: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_browser())
    print("\nTest Result:", "SUCCESS" if success else "FAILED")
    sys.exit(0 if success else 1)