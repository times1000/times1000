"""
main.py - Entry point for the Times1000 application with supervisor agent orchestration

This script implements a supervisor agent that delegates tasks to specialized agents:
- CodeAgent: Handles code writing, debugging, and explanation
- FilesystemAgent: Manages file operations and project organization
- SearchAgent: Performs web searches for information gathering
- BrowserAgent: Directly interacts with websites via browser automation

The supervisor follows a structured workflow:
1. Planning: Analyze requests and create step-by-step plans
2. Execution: Delegate tasks to specialized agents based on their capabilities
3. Verification: Ensure all success criteria are met
"""

import os
import sys
import json
import asyncio
import atexit
import contextlib
import argparse
import logging
from typing import List, Dict, Any, Optional
import textwrap

# Configure logging
logger = logging.getLogger(__name__)

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
from agents import ToolCallItem, ToolCallOutputItem, handoff, trace

from rich.markdown import Markdown
from rich.console import Console

# Import our browser computer implementation
from utils.browser_computer import LocalPlaywrightComputer

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
    last_tool_call = None
    current_agent = "Supervisor"

    # Create a streamed result
    result = Runner.run_streamed(agent, input_items)

    # Stream events as they occur
    async for event in result.stream_events():
        # Skip raw response events - these are the underlying API responses
        if event.type == "raw_response_event":
            continue

        # Handle agent updates (handoffs and tool calls)
        elif event.type == "agent_updated_stream_event":
            previous_agent = current_agent
            current_agent = event.new_agent.name
            # Check if this is a handoff
            is_handoff = hasattr(event, 'handoff') and event.handoff

            if is_handoff:
                # This is a handoff - show more detailed handoff information
                handoff_source = previous_agent if previous_agent else "Supervisor"
                print(f"\n🔄 HANDOFF: {handoff_source} → {current_agent}")
                print(f"Conversation control transferred to specialized {current_agent}")

                # Add special indicators for specific agent types
                if "Browser" in current_agent:
                    print("🌐 Web browsing task delegated to browser specialist")
                elif "Code" in current_agent:
                    print("💻 Programming task delegated to code specialist")
                elif "Filesystem" in current_agent:
                    print("📁 File operation task delegated to filesystem specialist")
                elif "Search" in current_agent:
                    print("🔍 Search task delegated to search specialist")
            else:
                # This is a regular agent transition
                print(f"\nAgent: {current_agent}")

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
                        # Track which agent is being called
                        tool_name = raw_item.name
                        last_tool_call = tool_name

                        if tool_name == "browser_agent" or tool_name == "browser_agent_tool":
                            print(f"\nBrowserAgent: Working...")

                            # Fix for double-encoded JSON - check if the input is a string that contains JSON
                            if hasattr(raw_item, 'parameters') and isinstance(raw_item.parameters, dict) and 'input' in raw_item.parameters:
                                input_param = raw_item.parameters['input']
                                if isinstance(input_param, str) and input_param.startswith('{') and input_param.endswith('}'):
                                    try:
                                        # Try to parse as JSON with single quote support
                                        parsed_input = json.loads(input_param.replace("'", '"'))
                                        # Replace with parsed object
                                        raw_item.parameters['input'] = parsed_input
                                    except json.JSONDecodeError:
                                        # Try to fix common Python dict formatting
                                        try:
                                            # Use ast.literal_eval for Python dict strings
                                            import ast
                                            parsed_input = ast.literal_eval(input_param)
                                            raw_item.parameters['input'] = parsed_input
                                        except Exception:
                                            # Not valid Python dict either, leave as is
                                            pass

                            # Fix for passing parameters to playwright_navigate
                            if hasattr(raw_item, 'parameters') and isinstance(raw_item.parameters, dict):
                                # Check for direct parameters to tools like playwright_navigate
                                for key, value in raw_item.parameters.items():
                                    if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                                        try:
                                            # Try to parse JSON string as object, replacing single quotes with double quotes
                                            parsed_value = json.loads(value.replace("'", '"'))
                                            # Replace with parsed object
                                            raw_item.parameters[key] = parsed_value
                                        except json.JSONDecodeError:
                                            # Try ast.literal_eval for Python dict strings
                                            try:
                                                import ast
                                                parsed_value = ast.literal_eval(value)
                                                raw_item.parameters[key] = parsed_value
                                            except Exception:
                                                # Not valid Python dict either, leave as is
                                                pass
                        elif tool_name == "planner_agent":
                            print(f"\nPlanner: Analyzing task and creating execution plan...")
                            # Parse planner parameters
                            if hasattr(raw_item, 'parameters') and isinstance(raw_item.parameters, dict):
                                try:
                                    task = raw_item.parameters.get('task', '')
                                    if task:
                                        print(f"Planning task: {task[:100]}..." if len(task) > 100 else f"Planning task: {task}")
                                except (AttributeError, KeyError) as e:
                                    logger.warning(f"Error parsing planner parameters: {e}")
                                    pass

                        elif tool_name == "worker_agent":
                            print(f"\nWorker: Executing task...")
                            # Parse worker parameters
                            if hasattr(raw_item, 'parameters') and isinstance(raw_item.parameters, dict):
                                try:
                                    task_instructions = raw_item.parameters.get('task_instructions', '')
                                    complexity = raw_item.parameters.get('complexity', 'simple')

                                    if task_instructions:
                                        print(f"Task: {task_instructions[:100]}..." if len(task_instructions) > 100 else f"Task: {task_instructions}")

                                    if complexity == "complex":
                                        print("Using enhanced reasoning (complex task mode)")
                                except (AttributeError, KeyError) as e:
                                    logger.warning(f"Error parsing worker parameters: {e}")
                                    pass
                        else:
                            print(f"\n{agent_name}: Calling tool {tool_name}")

            elif item.type == "tool_call_output_item":
                # Format output concisely
                try:
                    if isinstance(item.output, str) and (item.output.startswith('{') or item.output.startswith('[')):
                        # For JSON output, don't show duplicative information
                        pass
                    else:
                        # Determine which agent generated this result based on last tool call
                        if last_tool_call == "browser_agent":
                            print(f"\nBrowserAgent result: {item.output}")
                        elif last_tool_call == "planner_agent":
                            # Try to extract key plan info for display
                            try:
                                if isinstance(item.output, str):
                                    if "SUCCESS CRITERIA" in item.output.upper():
                                        print(f"\nPlanner result: Plan created successfully with defined success criteria")
                                    else:
                                        print(f"\nPlanner result: Plan created successfully")
                                else:
                                    print(f"\nPlanner result: Plan created successfully")
                            except:
                                print(f"\nPlanner result: Plan created successfully")
                        elif last_tool_call == "worker_agent":
                            # Try to extract completion status from output
                            try:
                                if isinstance(item.output, str):
                                    if "COMPLETED" in item.output.upper() or "SUCCESS" in item.output.upper():
                                        print(f"\nWorker result: Task execution completed successfully")
                                    elif "PARTIAL" in item.output.upper():
                                        print(f"\nWorker result: Task execution partially completed")
                                    elif "FAIL" in item.output.upper() or "ERROR" in item.output.upper():
                                        print(f"\nWorker result: Task execution encountered problems")
                                    else:
                                        print(f"\nWorker result: Task execution completed")
                                else:
                                    print(f"\nWorker result: Task execution completed")
                            except:
                                print(f"\nWorker result: Task execution completed")
                        else:
                            print(f"\n{agent_name} result: {item.output}")

                        # Reset the tracking after using it
                        last_tool_call = None
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
        history_dir = os.path.join(home_dir, ".times1000_history")

        # Create directory if it doesn't exist
        os.makedirs(history_dir, exist_ok=True)
        histfile = os.path.join(history_dir, "history")

        # If we still can't access the history file location, fallback to current directory
        if not os.access(history_dir, os.W_OK):
            # Use current directory as fallback
            histfile = os.path.join(os.getcwd(), ".times1000_history")

        # Set history length
        readline.set_history_length(1000)

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

    # Browser computer will be initialized when needed (lazy loading)

    # Create the supervisor agent with parallel execution capabilities
    agent = await create_supervisor_agent(init_browser)

    # Initialize conversation history
    input_items: List = []

    # Display welcome message with available functionality
    print("\nSupervisor Ready.")

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
