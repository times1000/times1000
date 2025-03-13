#!/usr/bin/env python
"""
Test script to verify browser agent functionality
"""

import asyncio
import sys
from core_agents.browser_agent import create_browser_agent
from utils.browser_computer import LocalPlaywrightComputer
from utils import BrowserSessionContext
from agents import Runner, ItemHelpers

async def test_browser_agent():
    print("Testing browser agent...")
    try:
        # Create browser agent
        agent = await create_browser_agent()
        print("Browser agent created successfully!")
        
        # Test basic navigation
        print("\nTesting browser navigation...")
        input_items = [{"content": "Go to https://example.com and tell me what you see", "role": "user"}]
        
        # Run is a coroutine in newer versions
        if asyncio.iscoroutinefunction(Runner.run):
            result = await Runner.run(agent, input_items)
        else:
            result = Runner.run(agent, input_items)
        
        print("Navigation test completed!")
        
        # Get the result content
        if hasattr(result, 'items'):
            for item in result.items:
                if item.type == "message_output_item":
                    print("\nAgent response:", ItemHelpers.text_message_output(item)[:200] + "...")
                    break
        
        # Clean up
        from core_agents.browser_agent import cleanup_browser_agent
        print("\nCleaning up browser agent...")
        await cleanup_browser_agent(agent)
        print("Browser agent cleaned up successfully!")
        
        return True
    except Exception as e:
        print(f"Error during test: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_browser_agent())
    print("\nTest Result:", "SUCCESS" if success else "FAILED")
    sys.exit(0 if success else 1)