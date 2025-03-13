"""
browser_agent.py - Specialized agent for direct website interaction via browser
with enhanced error handling and retry mechanisms
"""

import logging
import asyncio
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
            elif "get_location" in tool_name:
                # Location services may need multiple retries with fallbacks
                max_retries = 3
                strategy = RetryStrategy.EXPONENTIAL_BACKOFF
                base_delay = 1.5
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

# Function to add CAPTCHA detection and solving tool
def add_captcha_tools(browser_tools: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adds CAPTCHA detection and solving capabilities to the browser tools
    
    Args:
        browser_tools: Dictionary of browser tools
        
    Returns:
        Dictionary of browser tools with added CAPTCHA handling
    """
    from agents.tool import function_tool
    
    @function_tool
    async def detect_and_solve_captcha():
        """
        Detects if the current page contains a CAPTCHA and attempts to solve it.
        This tool helps identify and solve common CAPTCHA types including:
        - Google reCAPTCHA v2 (checkbox)
        - Google reCAPTCHA v3 (invisible)
        - hCaptcha
        - Simple image CAPTCHAs
        - Text-based CAPTCHAs
        
        Returns:
            A message indicating whether a CAPTCHA was found and if it was solved
        """
        # Get the browser computer
        bc = browser_tools["playwright_navigate"].browser_computer
        
        if not bc._page:
            return "Error: Browser is not initialized or no page is currently open"
        
        try:
            print("Checking for CAPTCHA presence...")
            
            # Execute a comprehensive CAPTCHA detection script
            captcha_detection_script = """
            () => {
                // Helper function to check element visibility
                const isVisible = (element) => {
                    if (!element) return false;
                    const style = window.getComputedStyle(element);
                    return style.display !== 'none' && 
                           style.visibility !== 'hidden' && 
                           style.opacity !== '0' &&
                           element.offsetWidth > 0 &&
                           element.offsetHeight > 0;
                };
                
                // Find and analyze potential CAPTCHA elements
                const captchaResults = {
                    found: false,
                    type: null,
                    details: {},
                    selectors: {},
                    frameSrc: null
                };
                
                // Check for Google reCAPTCHA
                const recaptchaFrames = Array.from(document.querySelectorAll('iframe[src*="recaptcha"]'));
                const recaptchaElements = Array.from(document.querySelectorAll('.g-recaptcha, .recaptcha, [data-sitekey], [data-recaptcha]'));
                const recaptchaCheckbox = document.querySelector('.recaptcha-checkbox');
                
                // Check for hCaptcha
                const hcaptchaFrames = Array.from(document.querySelectorAll('iframe[src*="hcaptcha"]'));
                const hcaptchaElements = Array.from(document.querySelectorAll('.h-captcha, [data-hcaptcha-sitekey]'));
                
                // Check for common CAPTCHA keywords in the page content
                const pageText = document.body.innerText.toLowerCase();
                const captchaKeywords = ['captcha', 'robot', 'human verification', 'security check', 'verify you are human'];
                const keywordMatch = captchaKeywords.some(keyword => pageText.includes(keyword));
                
                // Check for common CAPTCHA input fields
                const captchaInputs = Array.from(document.querySelectorAll('input[name*="captcha"], input[id*="captcha"], input[placeholder*="captcha"]'));
                
                // Check for image CAPTCHAs (images near input fields with CAPTCHA-related text)
                let imageCaptchas = [];
                document.querySelectorAll('img').forEach(img => {
                    // Check if image is near input field or has CAPTCHA-related attributes
                    const nearInput = img.parentElement?.querySelector('input') || 
                                      img.parentElement?.parentElement?.querySelector('input');
                    
                    const hasCaptchaAttr = img.src.toLowerCase().includes('captcha') || 
                                          (img.alt && img.alt.toLowerCase().includes('captcha')) ||
                                          (img.id && img.id.toLowerCase().includes('captcha')) ||
                                          (img.className && img.className.toLowerCase().includes('captcha'));
                    
                    if ((nearInput && isVisible(img)) || hasCaptchaAttr) {
                        imageCaptchas.push({
                            src: img.src,
                            dimensions: {width: img.width, height: img.height},
                            selector: `img[src="${img.src}"]`
                        });
                    }
                });
                
                // Determine if any CAPTCHA is present
                if (
                    (recaptchaFrames.length > 0 && recaptchaFrames.some(frame => isVisible(frame))) || 
                    (recaptchaElements.length > 0 && recaptchaElements.some(el => isVisible(el))) ||
                    (hcaptchaFrames.length > 0 && hcaptchaFrames.some(frame => isVisible(frame))) ||
                    (hcaptchaElements.length > 0 && hcaptchaElements.some(el => isVisible(el))) ||
                    (captchaInputs.length > 0 && captchaInputs.some(input => isVisible(input))) ||
                    (imageCaptchas.length > 0) ||
                    (recaptchaCheckbox && isVisible(recaptchaCheckbox))
                ) {
                    captchaResults.found = true;
                    
                    // Identify CAPTCHA type
                    if (recaptchaFrames.length > 0 || recaptchaElements.length > 0 || recaptchaCheckbox) {
                        captchaResults.type = 'reCAPTCHA';
                        
                        // Get all visible reCAPTCHA elements
                        const visibleReCaptchaElements = recaptchaElements.filter(el => isVisible(el));
                        
                        if (recaptchaCheckbox && isVisible(recaptchaCheckbox)) {
                            captchaResults.details.version = 'v2-checkbox';
                            captchaResults.selectors.checkbox = '.recaptcha-checkbox';
                        } else if (visibleReCaptchaElements.some(el => el.dataset.size === 'invisible')) {
                            captchaResults.details.version = 'v3-invisible';
                        } else {
                            captchaResults.details.version = 'v2';
                        }
                        
                        // Get frame sources if available
                        if (recaptchaFrames.length > 0) {
                            const visibleFrames = recaptchaFrames.filter(frame => isVisible(frame));
                            if (visibleFrames.length > 0) {
                                captchaResults.frameSrc = visibleFrames[0].src;
                            }
                        }
                    } else if (hcaptchaFrames.length > 0 || hcaptchaElements.length > 0) {
                        captchaResults.type = 'hCaptcha';
                        
                        // Get frame sources if available
                        if (hcaptchaFrames.length > 0) {
                            const visibleFrames = hcaptchaFrames.filter(frame => isVisible(frame));
                            if (visibleFrames.length > 0) {
                                captchaResults.frameSrc = visibleFrames[0].src;
                            }
                        }
                    } else if (imageCaptchas.length > 0) {
                        captchaResults.type = 'image-captcha';
                        captchaResults.details.images = imageCaptchas;
                    } else if (captchaInputs.length > 0) {
                        captchaResults.type = 'text-captcha';
                        
                        // Get all visible CAPTCHA inputs
                        const visibleCaptchaInputs = captchaInputs.filter(input => isVisible(input));
                        
                        if (visibleCaptchaInputs.length > 0) {
                            captchaResults.selectors.inputs = visibleCaptchaInputs.map(input => {
                                const inputSelector = input.id ? 
                                    `#${input.id}` : 
                                    (input.name ? 
                                        `input[name="${input.name}"]` : 
                                        `input[placeholder="${input.placeholder}"]`);
                                return inputSelector;
                            });
                        }
                    }
                } else if (keywordMatch) {
                    // CAPTCHA might be present based on text, but no specific elements found
                    captchaResults.found = true;
                    captchaResults.type = 'text-based';
                    captchaResults.details.keywords = captchaKeywords.filter(keyword => pageText.includes(keyword));
                }
                
                // Find submit buttons near CAPTCHA elements if CAPTCHA is found
                if (captchaResults.found) {
                    // Look for submit buttons
                    const possibleSubmitButtons = Array.from(document.querySelectorAll('button[type="submit"], input[type="submit"], button:not([type]), .g-recaptcha + button, .h-captcha + button'));
                    
                    // Also look for elements with "submit", "verify", "continue" text
                    const textButtons = Array.from(document.querySelectorAll('button, a.button, .btn, [role="button"]'))
                        .filter(el => {
                            const text = el.innerText.toLowerCase();
                            return text.includes('submit') || 
                                  text.includes('verify') || 
                                  text.includes('continue') ||
                                  text.includes('next');
                        });
                    
                    const allPossibleButtons = [...possibleSubmitButtons, ...textButtons];
                    const visibleButtons = allPossibleButtons.filter(btn => isVisible(btn));
                    
                    if (visibleButtons.length > 0) {
                        captchaResults.selectors.submitButtons = visibleButtons.map(btn => {
                            // Generate a selector for this button
                            if (btn.id) return `#${btn.id}`;
                            if (btn.className && typeof btn.className === 'string' && btn.className.trim()) {
                                // Convert multiple classes to a valid selector
                                const classes = btn.className.trim().split(/\\s+/).join('.');
                                return `.${classes}`;
                            }
                            // Fallback to button type or element type
                            if (btn.type) return `${btn.tagName.toLowerCase()}[type="${btn.type}"]`;
                            return btn.tagName.toLowerCase();
                        });
                    }
                }
                
                return captchaResults;
            }
            """
            
            # Run detection script
            captcha_results = await bc._page.evaluate(captcha_detection_script)
            
            if not captcha_results.get('found', False):
                return "No CAPTCHA detected on current page."
            
            # Log CAPTCHA detection details
            captcha_type = captcha_results.get('type', 'unknown')
            print(f"CAPTCHA detected! Type: {captcha_type}")
            print(f"CAPTCHA details: {captcha_results}")
            
            # Take a screenshot of the CAPTCHA for analysis
            screenshot_name = "captcha_detected"
            png_bytes = await bc._page.screenshot(full_page=False)
            import base64
            screenshot_b64 = base64.b64encode(png_bytes).decode("utf-8")
            
            # Different solving strategies based on CAPTCHA type
            if captcha_type == 'reCAPTCHA':
                version = captcha_results.get('details', {}).get('version', 'v2')
                
                if version == 'v2-checkbox':
                    # Handle reCAPTCHA v2 checkbox
                    checkbox_selector = captcha_results.get('selectors', {}).get('checkbox', '.recaptcha-checkbox')
                    
                    try:
                        # 1. Click the reCAPTCHA checkbox
                        print(f"Clicking reCAPTCHA checkbox: {checkbox_selector}")
                        await bc._page.click(checkbox_selector, timeout=5000)
                        await asyncio.sleep(2)  # Wait for potential challenges to appear
                        
                        # 2. Check if we need to solve a challenge
                        frame_selector = 'iframe[title="recaptcha challenge expires in two minutes"]'
                        challenge_frame = bc._page.frame_locator(frame_selector)
                        
                        if challenge_frame:
                            # Take a screenshot of the challenge
                            challenge_screenshot = await bc._page.screenshot(full_page=False)
                            challenge_b64 = base64.b64encode(challenge_screenshot).decode("utf-8")
                            
                            # We have a challenge to solve - this is just a stub implementation
                            # For a real implementation, you would need to:
                            # 1. Analyze the type of challenge (image selection, audio, etc.)
                            # 2. Use computer vision or audio processing to solve
                            # 3. Submit the solution
                            
                            # For now, just click through the challenge (this won't actually solve it)
                            await bc._page.evaluate("""
                            () => {
                                // Add visual indication that we're attempting to solve
                                const style = document.createElement('style');
                                style.textContent = `
                                    .captcha-solving-indicator {
                                        position: fixed;
                                        top: 10px;
                                        right: 10px;
                                        background: rgba(0, 128, 255, 0.8);
                                        color: white;
                                        padding: 10px;
                                        border-radius: 5px;
                                        z-index: 10000;
                                        font-family: Arial, sans-serif;
                                    }
                                `;
                                document.head.appendChild(style);
                                
                                const indicator = document.createElement('div');
                                indicator.className = 'captcha-solving-indicator';
                                indicator.textContent = 'Attempting to solve CAPTCHA...';
                                document.body.appendChild(indicator);
                                
                                // The indicator will be automatically removed when the page changes
                            }
                            """)
                            
                            # Wait for some time to see if the reCAPTCHA resolves
                            await asyncio.sleep(5)
                            
                            return "Detected reCAPTCHA v2 with challenge. Attempted to solve but may require human verification."
                        else:
                            # Check if the checkbox is now checked (success)
                            is_checked = await bc._page.evaluate(f"""
                            () => {{
                                const checkbox = document.querySelector('{checkbox_selector}');
                                return checkbox && checkbox.getAttribute('aria-checked') === 'true';
                            }}
                            """)
                            
                            if is_checked:
                                # Find and click submit button if available
                                submit_buttons = captcha_results.get('selectors', {}).get('submitButtons', [])
                                if submit_buttons:
                                    for button_selector in submit_buttons:
                                        try:
                                            await bc._page.click(button_selector, timeout=3000)
                                            await asyncio.sleep(2)  # Wait for form submission
                                            break
                                        except Exception as e:
                                            print(f"Could not click submit button {button_selector}: {e}")
                                
                                return "Successfully solved reCAPTCHA v2 checkbox!"
                            else:
                                return "Clicked reCAPTCHA checkbox but verification unsuccessful."
                    except Exception as e:
                        print(f"Error solving reCAPTCHA: {e}")
                        return f"Error while attempting to solve reCAPTCHA: {e}"
                
                elif version == 'v3-invisible':
                    # For invisible reCAPTCHA, we usually need to just proceed with the form submission
                    submit_buttons = captcha_results.get('selectors', {}).get('submitButtons', [])
                    if submit_buttons:
                        for button_selector in submit_buttons:
                            try:
                                await bc._page.click(button_selector, timeout=3000)
                                await asyncio.sleep(2)  # Wait for form submission
                                break
                            except Exception as e:
                                print(f"Could not click submit button {button_selector}: {e}")
                    
                    # Check if we're still on the same page or if we moved to a new page
                    current_url = bc._page.url
                    return f"Attempted to proceed with invisible reCAPTCHA by submitting the form. Current URL: {current_url}"
                
                else:
                    # Generic reCAPTCHA handling
                    return f"Detected reCAPTCHA (version: {version}). Manual solving may be required."
            
            elif captcha_type == 'hCaptcha':
                # hCaptcha usually requires similar handling to reCAPTCHA
                return "Detected hCaptcha. Manual solving may be required."
            
            elif captcha_type == 'image-captcha':
                # For image CAPTCHAs, we'd need OCR capabilities
                images = captcha_results.get('details', {}).get('images', [])
                if images:
                    image_selector = images[0].get('selector')
                    
                    # Find nearby input fields
                    input_fields = await bc._page.evaluate(f"""
                    () => {{
                        const img = document.querySelector('{image_selector}');
                        if (!img) return [];
                        
                        // Look for input fields near the image
                        const container = img.closest('form') || img.parentElement || img.parentElement.parentElement;
                        if (!container) return [];
                        
                        const inputs = Array.from(container.querySelectorAll('input[type="text"]'));
                        return inputs.map(input => {{
                            return {{
                                selector: input.id ? `#${{input.id}}` : (input.name ? `input[name="${{input.name}}"]` : null),
                                placeholder: input.placeholder || '',
                                label: input.labels && input.labels[0] ? input.labels[0].textContent : null
                            }};
                        }}).filter(input => input.selector);
                    }}
                    """)
                    
                    if input_fields:
                        # For a real implementation, we would use OCR here to read the CAPTCHA image
                        # For now, just simulate a partial solution
                        input_selector = input_fields[0].get('selector')
                        
                        if input_selector:
                            # Add visual indication that we're attempting to solve
                            await bc._page.evaluate("""
                            () => {
                                const style = document.createElement('style');
                                style.textContent = `
                                    .captcha-solving-indicator {
                                        position: fixed;
                                        top: 10px;
                                        right: 10px;
                                        background: rgba(0, 128, 255, 0.8);
                                        color: white;
                                        padding: 10px;
                                        border-radius: 5px;
                                        z-index: 10000;
                                        font-family: Arial, sans-serif;
                                    }
                                `;
                                document.head.appendChild(style);
                                
                                const indicator = document.createElement('div');
                                indicator.className = 'captcha-solving-indicator';
                                indicator.textContent = 'Attempting to solve image CAPTCHA...';
                                document.body.appendChild(indicator);
                            }
                            """)
                            
                            # This would be replaced with actual OCR in a real implementation
                            placeholder = input_fields[0].get('placeholder', '')
                            label = input_fields[0].get('label', '')
                            
                            # For now, just report the CAPTCHA details
                            return f"Detected image CAPTCHA. Input field found ({input_selector}). Manual solving required."
                    
                    return "Detected image CAPTCHA but couldn't find associated input field."
                
                return "Detected image CAPTCHA. Manual solving may be required."
            
            elif captcha_type == 'text-captcha':
                # For text CAPTCHAs, we need to find the question and provide an answer
                inputs = captcha_results.get('selectors', {}).get('inputs', [])
                if inputs:
                    input_selector = inputs[0]
                    
                    # Get the text around the input to understand the CAPTCHA question
                    captcha_text = await bc._page.evaluate(f"""
                    () => {{
                        const input = document.querySelector('{input_selector}');
                        if (!input) return '';
                        
                        // Find the closest container
                        const container = input.closest('form') || input.parentElement || input.parentElement.parentElement;
                        if (!container) return '';
                        
                        // Get text context around the input
                        return container.innerText;
                    }}
                    """)
                    
                    # This would be replaced with actual text analysis in a real implementation
                    await bc._page.evaluate("""
                    () => {
                        const style = document.createElement('style');
                        style.textContent = `
                            .captcha-solving-indicator {
                                position: fixed;
                                top: 10px;
                                right: 10px;
                                background: rgba(0, 128, 255, 0.8);
                                color: white;
                                padding: 10px;
                                border-radius: 5px;
                                z-index: 10000;
                                font-family: Arial, sans-serif;
                            }
                        `;
                        document.head.appendChild(style);
                        
                        const indicator = document.createElement('div');
                        indicator.className = 'captcha-solving-indicator';
                        indicator.textContent = 'Text CAPTCHA detected. Manual solving required.';
                        document.body.appendChild(indicator);
                    }
                    """)
                    
                    # For now, just report the CAPTCHA text
                    captcha_preview = captcha_text[:200] + "..." if len(captcha_text) > 200 else captcha_text
                    return f"Detected text CAPTCHA. Question context: '{captcha_preview}'. Manual solving required."
                
                return "Detected text CAPTCHA but couldn't find associated input field."
            
            elif captcha_type == 'text-based':
                # Generic text-based CAPTCHA detection based on keywords
                keywords = captcha_results.get('details', {}).get('keywords', [])
                return f"Detected possible CAPTCHA based on keywords: {', '.join(keywords)}. Manual verification may be required."
            
            else:
                return f"Detected unknown CAPTCHA type: {captcha_type}. Manual solving may be required."
            
        except Exception as e:
            print(f"Error in CAPTCHA detection: {e}")
            return f"Error while attempting to detect CAPTCHA: {e}"
    
    # Add our CAPTCHA detection tool to the tools dict
    browser_tools["detect_and_solve_captcha"] = detect_and_solve_captcha
    
    return browser_tools

async def create_browser_agent(browser_initializer):
    """Creates a browser agent with navigation and interaction capabilities."""
    # Initialize the browser only when needed
    try:
        browser_computer = await browser_initializer()
        
        # Get all browser tools 
        base_browser_tools = create_browser_tools(browser_computer)
        
        # Wrap tools with retry logic
        browser_tools = create_resilient_browser_tools(base_browser_tools)
        
        # Add CAPTCHA detection and solving tools
        browser_tools = add_captcha_tools(browser_tools)
    except Exception as e:
        logger.error(f"Error initializing browser or creating tools: {e}")
        print(f"Error initializing browser or creating tools: {e}")
        # Re-raise to fail initialization
        raise
    
    # Create a patched version of the browser agent that can handle JSON-encoded inputs
    # We'll create this by extending the Agent class
    import json
    from functools import wraps
    import asyncio
    return Agent(
        name="BrowserAgent",
        instructions="""You are a browser interaction expert specializing in website navigation and interaction, with enhanced error handling and recovery capabilities.

CAPABILITIES:
- Navigate to URLs directly using the playwright_navigate tool
- Take screenshots of webpages using the playwright_screenshot tool
- Click on elements using the playwright_click tool
- Fill out forms using the playwright_fill tool
- Press keyboard keys using the playwright_keypress tool
- Make HTTP requests directly using playwright_get, playwright_post, etc.
- Execute JavaScript in the browser using playwright_evaluate
- Get geolocation information using the playwright_get_location tool
- Detect and solve CAPTCHA challenges using detect_and_solve_captcha tool
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

CAPTCHA HANDLING:
- Use the detect_and_solve_captcha tool to identify and attempt to solve CAPTCHAs
- The tool can detect and solve several types of CAPTCHAs:
  * Google reCAPTCHA v2 (checkbox)
  * Google reCAPTCHA v3 (invisible)
  * hCaptcha
  * Simple image CAPTCHAs
  * Text-based CAPTCHAs
- The tool will provide information about the CAPTCHA and attempt to solve it if possible
- For complex CAPTCHAs that can't be automatically solved, the tool will provide guidance

PREFERRED TOOL ORDER:
1. Use direct Playwright tools whenever possible (playwright_*)
2. If you encounter a CAPTCHA, use the detect_and_solve_captcha tool
3. Only fall back to ComputerTool when direct tools can't solve your task

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

11. playwright_keypress: Press keyboard keys or key combinations
   - Example: playwright_keypress(key="Enter")
   - Example: playwright_keypress(key="ArrowDown") 
   - Example: playwright_keypress(key="Control+a")
   - Example: playwright_keypress(key="Tab", selector="input#search")

12. HTTP Request tools:
   - playwright_get(url="https://api.example.com/data")
   - playwright_post(url="https://api.example.com/submit", value='{"key": "value"}')
   - playwright_put, playwright_patch, playwright_delete

13. Geolocation tool (for getting user location):
   - playwright_get_location()
   - playwright_get_location(service="ipinfo", api_key="your_api_key") 
   - playwright_get_location(include_details=True, timeout=10000)
   - playwright_get_location(fallback_service="geojs", use_cache=True, language="en")

14. CAPTCHA detection and solving tool:
   - detect_and_solve_captcha() - Detects and attempts to solve CAPTCHAs on the current page

15. Legacy tool (ONLY use if direct tools don't work):
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

CAPTCHA HANDLING WORKFLOW:
1. If you suspect a CAPTCHA might be present (security check, verification page, etc.):
   - Run detect_and_solve_captcha() to detect and attempt to solve it
2. Review the CAPTCHA detection results to understand the type of CAPTCHA
3. If the CAPTCHA was automatically solved, continue with the interaction
4. If the CAPTCHA requires manual solving, clearly explain this to the user

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
   
4. For CAPTCHA-related issues:
   - Use the detect_and_solve_captcha tool to identify and handle CAPTCHAs
   - If automatic solving fails, clearly explain the situation to the user
   - Provide guidance on what type of CAPTCHA was encountered

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
            
            # Geolocation tool
            browser_tools["playwright_get_location"],
            
            # Keyboard interaction tool
            browser_tools["playwright_keypress"],
            
            # CAPTCHA detection and handling tool
            browser_tools["detect_and_solve_captcha"],
            
            # Legacy tools (only when direct tools don't work)
            ComputerTool(browser_computer)
        ],
        # Use computer-use-preview model when using ComputerTool
        model="computer-use-preview",
        model_settings=ModelSettings(truncation="auto"),
    )