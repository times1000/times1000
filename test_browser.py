#!/usr/bin/env python3
"""
Test script for debugging browser functionality.
"""

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def test_browser():
    """Simple test of browser functionality."""
    print("Starting browser test...")
    
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=False)
        
        print("Creating page...")
        page = await browser.new_page()
        
        url = "https://example.com"
        print(f"Navigating to {url}...")
        
        try:
            # Test navigation
            await page.goto(url, wait_until="domcontentloaded")
            print("Navigation successful")
            
            # Test URL with error handling
            try:
                # Check if the url is a callable (method) or property
                url_attr = page.url
                if callable(url_attr):
                    current_url = await url_attr()
                else:
                    current_url = url_attr
                print(f"Current URL: {current_url}")
            except Exception as url_err:
                print(f"URL ERROR: {type(url_err).__name__}: {url_err}")
                import traceback
                traceback.print_exc()
                
            # Test title with error handling
            try:
                # Check if the title is a callable (method) or property
                title_attr = page.title
                if callable(title_attr):
                    page_title = await title_attr()
                else:
                    page_title = title_attr
                print(f"Page title: {page_title}")
            except Exception as title_err:
                print(f"TITLE ERROR: {type(title_err).__name__}: {title_err}")
                import traceback
                traceback.print_exc()
                
            # Print Playwright version for reference
            try:
                from importlib.metadata import version
                playwright_version = version('playwright')
                print(f"Playwright version: {playwright_version}")
            except:
                print("Could not determine Playwright version")
            
            # Test content extraction
            html_content = await page.content()
            print(f"Got HTML content ({len(html_content)} bytes)")
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text(separator='\n', strip=True)
            print(f"Text content preview: {text_content[:100]}...")
            
            # Test JavaScript execution with error handling
            print("\nExecuting JavaScript...")
            
            # Create a universal execute function that handles property vs method
            async def safe_execute_js(expr):
                evaluate_attr = page.evaluate
                if callable(evaluate_attr):
                    # Old style: evaluate is a method
                    return await evaluate_attr(expr)
                else:
                    # New style: evaluate is a property
                    return await page.evaluate(expr)
            
            try:
                # Test simple string using safe executor
                result1 = await safe_execute_js('document.title')
                print(f"JS result 1 (simple string): {result1}")
            except Exception as e1:
                print(f"JS ERROR 1: {type(e1).__name__}: {e1}")
                import traceback
                traceback.print_exc()
                
            try:
                # Test function syntax using safe executor
                result2 = await safe_execute_js('() => document.title')
                print(f"JS result 2 (function): {result2}")
            except Exception as e2:
                print(f"JS ERROR 2: {type(e2).__name__}: {e2}")
                import traceback
                traceback.print_exc()
                
            # Test script tag approach
            try:
                # Create a unique var name
                import time
                var_name = f"test_result_{int(time.time() * 1000)}"
                
                # Add script that sets a global variable
                await page.add_script_tag(content=f"""
                window.{var_name} = document.title;
                """)
                
                # Get the value from the global variable
                result3 = await safe_execute_js(f"window.{var_name}")
                print(f"JS result 3 (script tag): {result3}")
            except Exception as e3:
                print(f"JS ERROR 3: {type(e3).__name__}: {e3}")
                import traceback
                traceback.print_exc()
            
            # Test HTTP API
            print("\nTesting HTTP API...")
            context = await browser.new_context()
            api_response = await context.request.get("https://example.com")
            status = api_response.status
            print(f"API response status: {status}")
            
            api_text = await api_response.text()
            print(f"API response text preview: {api_text[:100]}...")
            
            await context.close()
            
        except Exception as e:
            print(f"Error during test: {type(e).__name__}: {e}")
        finally:
            print("Closing browser...")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_browser())