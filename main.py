"""
main.py - Entry point for the Times1000 application with parallel supervisor agent orchestration

This script implements a parallel supervisor agent that delegates tasks to specialized agents:
- CodeAgent: Handles code writing, debugging, and explanation
- FilesystemAgent: Manages file operations and project organization
- SearchAgent: Performs web searches for information gathering
- BrowserAgent: Directly interacts with websites via browser automation

The parallel supervisor follows a structured workflow:
1. Planning: Analyze requests, create step-by-step plans, and identify parallelization opportunities
2. Execution: Delegate tasks to specialized agents with dependency tracking and prioritization
3. Result Aggregation: Combine results from parallel task execution
4. Verification: Ensure all success criteria are met

The system supports:
- Concurrent execution of independent tasks
- Priority-based task scheduling
- Dependency tracking between related tasks
- Result aggregation from parallel executions
"""

import os
import sys
import json
import asyncio
import atexit
import contextlib
import argparse
from typing import List, Dict, Any, Optional
import textwrap

# Try to load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env file if it exists
except ImportError:
    # dotenv is not required, but it's a helpful convenience
    pass

# Platform-specific readline setup
try:
    # Try to use the gnureadline module on macOS for better compatibility
    if sys.platform == 'darwin':
        try:
            import gnureadline as readline
            readline_module = "gnureadline"
        except ImportError:
            import readline
            readline_module = "readline"
    else:
        import readline
        readline_module = "readline"
except ImportError:
    # Fallback if readline is not available
    readline = None
    readline_module = None

from agents import Agent, Runner, ItemHelpers, MessageOutputItem
from agents import ToolCallItem, ToolCallOutputItem, trace

from rich.markdown import Markdown
from rich.console import Console

# Import our browser computer implementation
from utils.browser_computer import LocalPlaywrightComputer

# Import our user interaction controller
from utils.user_interaction import UserInteractionController, QuestionPriority, QuestionCategory

# Import the supervisor agent creator from our core_agents package
from core_agents.supervisor import create_supervisor_agent

# Check for required environment variables
def check_api_keys():
    """Check if required API keys are set and provide helpful error messages if not."""
    if not os.environ.get("OPENAI_API_KEY"):
        error_message = textwrap.dedent("""
        ERROR: OpenAI API key is missing!
        
        You need to set the OPENAI_API_KEY environment variable to use this application.
        
        You can do this in one of the following ways:
        
        1. Set it for the current session (replace YOUR_API_KEY with your actual key):
           export OPENAI_API_KEY=YOUR_API_KEY  # Linux/macOS
           set OPENAI_API_KEY=YOUR_API_KEY     # Windows
        
        2. Add it to your shell profile (~/.bashrc, ~/.zshrc, etc.)
        
        3. Create a .env file in the project directory with:
           OPENAI_API_KEY=YOUR_API_KEY
        
        You can get an API key from: https://platform.openai.com/api-keys
        """)
        print(error_message)
        return False
    return True

# Process streamed response function
async def process_streamed_response(agent, input_items):
    # Create console for rich text rendering
    console = Console()
    
    # Track the last tool call to identify which agent a result belongs to
    last_browser_tool_call = False
    
    # Create a streamed result
    result = Runner.run_streamed(agent, input_items)

    # Stream events as they occur
    async for event in result.stream_events():
        # Skip raw response events - these are the underlying API responses
        if event.type == "raw_response_event":
            continue

        # Handle agent updates
        elif event.type == "agent_updated_stream_event":
            print(f"\nAgent: {event.new_agent.name}")

        # Handle run item stream events (most content comes through here)
        elif event.type == "run_item_stream_event":
            item = event.item
            agent_name = getattr(item, 'agent', agent).name

            # Handle different item types
            if item.type == "message_output_item":
                message_text = ItemHelpers.text_message_output(item)
                print(f"\n{agent_name}:")
                try:
                    console.print(Markdown(message_text))
                except Exception:
                    print(message_text)

            elif item.type == "tool_call_item":
                # Access the raw item if available
                if hasattr(item, 'raw_item'):
                    raw_item = item.raw_item
                    # Get tool name for function calls
                    if hasattr(raw_item, 'name'):
                        if raw_item.name == "browser_agent":
                            print(f"\nBrowserAgent: Working...")
                            last_browser_tool_call = True
                            
                            # Fix for double-encoded JSON - check if the input is a string that contains JSON
                            if hasattr(raw_item, 'parameters') and isinstance(raw_item.parameters, dict) and 'input' in raw_item.parameters:
                                input_param = raw_item.parameters['input']
                                if isinstance(input_param, str) and input_param.startswith('{') and input_param.endswith('}'):
                                    try:
                                        # Try to parse as JSON 
                                        parsed_input = json.loads(input_param)
                                        # Replace with parsed object
                                        raw_item.parameters['input'] = parsed_input
                                        print("Fixed double-encoded JSON input")
                                    except json.JSONDecodeError:
                                        # Not valid JSON, leave as is
                                        pass
                        else:
                            print(f"\n{agent_name}: Calling tool {raw_item.name}")
                            last_browser_tool_call = False

            elif item.type == "tool_call_output_item":
                # Format output concisely
                try:
                    if isinstance(item.output, str) and (item.output.startswith('{') or item.output.startswith('[')):
                        # For JSON output, don't show duplicative information
                        pass
                    else:
                        # Use last_browser_tool_call to determine if this is a result from the browser agent
                        if last_browser_tool_call:
                            print(f"\nBrowserAgent result: {item.output}")
                            # Reset the flag after using it
                            last_browser_tool_call = False
                        else:
                            print(f"\n{agent_name} result: {item.output}")
                except:
                    pass

    # Return the result for updating conversation history
    return result

# Setup command history with readline
def setup_readline():
    """Sets up readline with command history if possible, otherwise disables it."""
    # Check if readline module is available
    if readline is None:
        print("Readline module not available. Command history disabled.")
        return False
        
    # Skip readline setup if we're in an environment that doesn't support it well
    if not sys.stdin.isatty():
        return False
        
    try:
        # Use a persistent history file in the user's home directory
        home_dir = os.path.expanduser("~")
        history_dir = os.path.join(home_dir, ".times2000_history")
        
        # Create directory if it doesn't exist
        os.makedirs(history_dir, exist_ok=True)
        histfile = os.path.join(history_dir, "history")
        
        # If we still can't access the history file location, fallback to current directory
        if not os.access(history_dir, os.W_OK):
            # Use current directory as fallback
            histfile = os.path.join(os.getcwd(), ".times2000_history")
        
        # Set history length
        readline.set_history_length(1000)
        
        # Add a test entry to history to verify it works
        readline.add_history("test command")
        
        # Configure readline based on which module we're using
        if readline_module == "gnureadline":
            # GNU readline has consistent behavior
            readline.parse_and_bind("tab: complete")
            readline.parse_and_bind(r'"\e[A": previous-history')  # Up arrow
            readline.parse_and_bind(r'"\e[B": next-history')      # Down arrow
        elif sys.platform == 'darwin':  # macOS with standard readline
            # macOS libedit emulation
            readline.parse_and_bind("bind ^I rl_complete")
            readline.parse_and_bind("bind ^[[A ed-search-prev-history")
            readline.parse_and_bind("bind ^[[B ed-search-next-history")
        else:
            # Standard readline on other platforms
            readline.parse_and_bind("tab: complete")
            readline.parse_and_bind(r'"\e[A": previous-history')  # Up arrow
            readline.parse_and_bind(r'"\e[B": next-history')      # Down arrow
        
        # Save history on exit
        atexit.register(readline.write_history_file, histfile)
        
        # Try to read history file if it exists
        try:
            readline.read_history_file(histfile)
        except:
            # If reading fails, create a new file
            readline.write_history_file(histfile)
        
        return True
        
    except Exception as e:
        print(f"Warning: Readline functionality limited: {str(e)}")
        print("Command history will not be available for this session.")
        return False

# Safely get input with readline support when available
def safe_input(prompt, readline_available=True):
    """Safely get input with readline support when available."""
    if readline_available:
        # Use the standard input function to leverage readline capabilities
        try:
            return input(prompt)
        except EOFError:
            print("\nEOF detected. Exiting.")
            sys.exit(0)
        except KeyboardInterrupt:
            print("\nKeyboard interrupt detected. Exiting.")
            sys.exit(0)
        except Exception as e:
            print(f"\nInput error with readline: {str(e)}. Trying fallback method...")
            readline_available = False  # Fall back to direct stdin
    
    # Fallback method without readline
    if not readline_available:
        print(prompt, end='', flush=True)
        try:
            line = sys.stdin.readline()
            if not line:  # EOF
                print("\nEOF detected. Exiting.")
                sys.exit(0)
            return line.rstrip('\n')
        except KeyboardInterrupt:
            print("\nKeyboard interrupt detected. Exiting.")
            sys.exit(0)
        except Exception as e:
            print(f"\nCritical input error: {str(e)}. Exiting.")
            sys.exit(1)

# Main function to run the agent loop
async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the Supervisor Agent")
    parser.add_argument("-p", "--prompt", 
                        help="Initial prompt to run at startup", 
                        type=str)
    parser.add_argument("-t", "--test", 
                        help="Run a test prompt to verify browser agent functionality", 
                        action="store_true")
    parser.add_argument("--skip-key-check",
                        help="Skip the API key check (for testing only)",
                        action="store_true")
    parser.add_argument("--batch-questions",
                        help="Enable question batching to reduce interruptions",
                        type=str, choices=['true', 'false'], default='true')
    parser.add_argument("--batch-size",
                        help="Maximum number of questions to batch together",
                        type=int, default=3)
    parser.add_argument("--batch-timeout",
                        help="Maximum time (seconds) to wait before asking batched questions",
                        type=float, default=30.0)
    args = parser.parse_args()
    
    # Check for required API keys unless specifically skipped
    if not args.skip_key_check and not check_api_keys():
        sys.exit(1)
    
    # Setup readline for command history
    readline_available = setup_readline()
    
    # Initialize browser_computer as None - it will be created only when needed (lazy loading)
    browser_computer = None
    
    # Create the supervisor agent with a function to initialize the browser
    async def init_browser():
        nonlocal browser_computer
        if browser_computer is None:
            # Initialize browser when needed without verbose messages
            browser_computer = await LocalPlaywrightComputer(headless=False, silent=True).__aenter__()
            # Don't use atexit with asyncio.run() as it causes issues with closed event loops
            # We'll handle cleanup in the main loop exception handlers instead
        return browser_computer
    
    # Initialize user interaction controller for batching questions
    interaction_controller = UserInteractionController(
        max_batch_size=args.batch_size,
        batch_timeout_seconds=args.batch_timeout
    )
    
    # Create a function to ask a question through the interaction controller
    async def ask_user(question: str, 
                      category: QuestionCategory = QuestionCategory.OTHER,
                      priority: QuestionPriority = QuestionPriority.MEDIUM,
                      context: Dict[str, Any] = None,
                      timeout_seconds: Optional[float] = None) -> str:
        """Ask a question to the user through the interaction controller"""
        if args.batch_questions.lower() == 'true':
            return await interaction_controller.ask_question(
                question_text=question,
                category=category,
                priority=priority,
                context=context,
                timeout_seconds=timeout_seconds
            )
        else:
            # Direct question without batching if batching is disabled
            print(f"\n[QUESTION] {question}")
            if context:
                print("\nContext:")
                for key, value in context.items():
                    if not key.startswith('_'):  # Skip internal keys
                        print(f"- {key}: {value}")
            return await asyncio.get_event_loop().run_in_executor(None, input, "> ")
        
    # Create the supervisor agent with parallel execution capabilities
    agent = await create_supervisor_agent(init_browser)
    
    # Initialize conversation history
    input_items: List = []

    # Display welcome message with available functionality
    print("\nSupervisor Ready.")
    
    # Add a first message to the conversation to prime the agent
    input_items.append({
        "role": "system", 
        "content": """IMPORTANT AGENT SELECTION AND EXECUTION GUIDELINES:

PARALLEL EXECUTION CAPABILITIES:
- You can now execute multiple agent tasks in parallel
- Use these tools to manage parallel execution:
  * add_task: Queue a task for execution
  * execute_all_tasks: Run all queued tasks in parallel
  * get_result: Get results of a specific task
  * aggregate_results: Combine results from multiple tasks
  * cancel_task: Cancel a queued task that hasn't started

TASK PRIORITIZATION AND DEPENDENCIES:
- Assign priorities (HIGH, MEDIUM, LOW) to tasks
- Define dependencies between tasks when needed
- Independent tasks will execute in parallel
- Dependent tasks will wait for prerequisites to complete

AGENT SELECTION GUIDELINES:
1. For web browsing and website interaction tasks:
   - ALWAYS delegate to browser_agent
   - The browser_agent has direct Playwright tools:
     * playwright_navigate: For navigating to pages with configurable options
     * playwright_click: For clicking elements using CSS selectors
     * playwright_fill: For filling form inputs
     * playwright_screenshot: For taking screenshots
     * playwright_get/post/put/etc.: For direct HTTP API requests
     * Plus many more specialized tools for direct browser control
   - This includes ANY requests containing phrases like:
     * "go to website X"
     * "visit Y website"
     * "browse Z"
     * "check out site X"
     * "explore website Y"
     * "open Z in browser"
     * "interact with X"
     * "click on Y"
     * "fill out form"
     * "API request"
     * "reddit" or any specific website name

2. For information lookup and web searches:
   - Delegate to search_agent
   - This includes requests like:
     * "find information about X"
     * "search for Y"
     * "look up Z"
     * "research topic X"

Whenever a user mentions a specific website, web interaction, or browsing action, ALWAYS use browser_agent.
The browser_agent should always prefer direct Playwright tools over ComputerTool for faster, more reliable interactions."""
    })
    
    # Handle test prompt if specified (before the main loop)
    if args.test:
        print("\nRunning browser agent test...")
        
        # Test browser agent with a simple prompt
        test_prompt = "Go to https://example.com and tell me what you see on the page"
        print(f"Test prompt: {test_prompt}")
        
        # Run the test
        input_items.append({"content": test_prompt, "role": "user"})
        with trace("Test prompt processing"):
            result = await process_streamed_response(agent, input_items)
            input_items = result.to_input_list()
            print("Browser agent test completed.")
    
    # Handle initial prompt if specified (before the main loop)
    elif args.prompt:
        print(f"\nRunning initial prompt: {args.prompt}")
        input_items.append({"content": args.prompt, "role": "user"})
        with trace("Initial prompt processing"):
            result = await process_streamed_response(agent, input_items)
            input_items = result.to_input_list()
    
    try:
        while True:
            try:
                # Use appropriate input method
                user_input = safe_input("\n> ", readline_available)
                
                # Check for exit command
                if user_input.lower() in ('exit', 'quit'):
                    print("Exiting Supervisor Agent")
                    break
                    
                if user_input.strip():
                    # Add user input to conversation history
                    input_items.append({"content": user_input, "role": "user"})

                    # Process streamed response
                    with trace("Task processing"):
                        # Check if our agent is using the parallel implementation
                        if hasattr(agent, 'parallel_supervisor'):
                            # Using parallel execution
                            print("\nUsing parallel execution...")
                            
                        # Process the response as usual
                        result = await process_streamed_response(agent, input_items)

                        # Update input items with the result for the next iteration
                        input_items = result.to_input_list()
            except Exception as e:
                print(f"\nError processing input: {str(e)}")
                continue
    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Exiting.")
    finally:
        # Proper cleanup of browser if it was initialized
        if browser_computer is not None:
            try:
                await browser_computer.__aexit__(None, None, None)
            except Exception as e:
                print(f"Error during browser cleanup: {e}")
    
    print("Exiting application")

# Run the supervisor agent when this file is executed
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Exiting.")