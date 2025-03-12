"""
supervisor.py - A supervisor agent that orchestrates specialized agents for coding tasks

This script implements a supervisor agent that delegates tasks to specialized agents:
- CodeAgent: Handles code writing, debugging, and explanation
- FilesystemAgent: Manages file operations and project organization
- WebAgent: Performs web searches for information gathering

The supervisor follows a structured workflow:
1. Planning: Analyze requests and create step-by-step plans
2. Execution: Delegate tasks to specialized agents
3. Verification: Ensure all success criteria are met
"""

import os
import sys
import subprocess
import json
import asyncio
import atexit
import contextlib
from typing import Optional, List, AsyncContextManager

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

from agents import Agent, Runner, WebSearchTool, ItemHelpers, MessageOutputItem
from agents import ToolCallItem, ToolCallOutputItem, function_tool, trace
from agents import ComputerTool, ModelSettings

from rich.markdown import Markdown
from rich.console import Console

# Import our browser computer implementation
from browser_computer import LocalPlaywrightComputer

# Browser computer manager
class BrowserComputerManager:
    """Manages a LocalPlaywrightComputer instance for the application."""
    
    def __init__(self):
        self._computer = None
        
    async def get_computer(self) -> AsyncContextManager[LocalPlaywrightComputer]:
        """
        Returns a context manager for a LocalPlaywrightComputer.
        The computer will be created if it doesn't exist yet.
        """
        if self._computer is None:
            self._computer = LocalPlaywrightComputer(
                headless=False,
                browser_type="chromium",
                start_url="https://www.google.com"
            )
            
        @contextlib.asynccontextmanager
        async def _computer_context():
            try:
                # Enter the computer's context
                computer = await self._computer.__aenter__()
                yield computer
            finally:
                # We don't exit the context here to keep the browser open
                pass
                
        return _computer_context()
    
    async def close(self):
        """Close the browser if it's open."""
        if self._computer is not None:
            await self._computer.__aexit__(None, None, None)
            self._computer = None

# Create a singleton instance
browser_manager = BrowserComputerManager()

# Define custom tools
@function_tool
def run_claude_code(prompt: str, working_directory: Optional[str] = None) -> str:
    """
    Runs Claude Code CLI with the provided prompt to execute code tasks.
    Uses --print and --dangerously-skip-permissions flags for non-interactive execution.
    """
    try:
        # Run claude with specific flags for non-interactive usage
        command = ["claude", "--print", "--dangerously-skip-permissions", "-p", prompt]
        
        result = subprocess.run(
            command,
            cwd=working_directory,
            capture_output=True,
            text=True,
            check=False
        )
        
        # Check for any errors
        if result.returncode != 0:
            return f"ERROR: Claude execution failed with code {result.returncode}\nSTDERR: {result.stderr}"
        
        # Return the output
        return result.stdout
        
    except Exception as e:
        return f"Error executing Claude Code: {str(e)}"

@function_tool
def run_shell_command(command: str, working_directory: Optional[str] = None) -> str:
    """Execute a shell command."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_directory,
            capture_output=True,
            text=True,
            check=False
        )
        return f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n\nExit code: {result.returncode}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


# Define specialized agents
code_agent = Agent(
    name="CodeAgent",
    instructions="""You are a code expert specializing in writing, explaining, and modifying code.

When working with code:
1. Analyze requirements and existing code thoroughly
2. IMPORTANT: Do not try to implement code changes yourself
3. Delegate actual code implementation to Claude CLI
4. Specify requirements for clean, efficient code with proper error handling
5. Request maintenance of original style when modifying existing code

TOOLS AND USAGE:
You have access to run_claude_code:
- Purpose: Runs Claude Code CLI (another AI) to execute coding tasks
- IMPORTANT: Let Claude CLI do the actual coding work
- When using this tool, craft prompts with:
  * Clear task requirements and context
  * Specific instructions on what code to generate or modify
  * Any constraints or examples needed
- Claude CLI needs comprehensive context with each request

INTERACTING WITH CLAUDE CLI:
1. Analyze responses and refine prompts if needed
2. For unsatisfactory results:
   - Provide more specific instructions
   - Break down complex problems
   - Suggest alternative approaches
3. You may need multiple iterations to get optimal results

SELF-SUFFICIENCY PRINCIPLES:
1. Solve problems autonomously without user intervention
2. Try multiple approaches before asking for help
3. Only request user input as a last resort
4. Be specific if you must ask for help
    """,
    handoff_description="A specialized agent for writing, explaining and modifying code",
    tools=[run_claude_code],
)

filesystem_agent = Agent(
    name="FilesystemAgent",
    instructions="""You are a filesystem expert specializing in file operations and project structure.

When working with files and directories:
1. Organize project structures efficiently
2. Create appropriate directory hierarchies
3. Execute file operations (create, move, copy, delete)
4. Handle permissions and access issues
5. Use error handling for file operations

TOOLS AND USAGE:
run_shell_command:
- Executes shell commands for file manipulation and system queries
- Use for creating directories (mkdir), listing files (ls), moving (mv), copying (cp), etc.
- Can specify an optional working directory
- Returns stdout, stderr, and exit code for debugging

SELF-SUFFICIENCY PRINCIPLES:
1. Work autonomously without user intervention
2. Use shell commands to gather filesystem information
3. When operations fail, try alternative approaches
4. Handle errors gracefully with fallback strategies
5. Only request user input as a last resort
    """,
    handoff_description="A specialized agent for file system operations and project organization",
    tools=[run_shell_command],
)

async def create_browser_agent():
    """Creates a browser agent with computer capabilities."""
    # Get a computer instance from the manager
    async with await browser_manager.get_computer() as computer:
        # Create the agent with computer tool only
        return Agent(
            name="BrowserAgent",
            instructions="""You are a web browser expert specializing in interacting with websites.

CAPABILITIES:
- Navigate to specific URLs
- Click on elements, fill out forms, and interact with content
- Scroll and navigate through pages
- Capture visual information from websites
- Extract data from web pages

TOOLS AND USAGE:
ComputerTool:
- Controls a web browser to interact with websites
- Captures screenshots to see website content
- Can click, type, scroll, and navigate within web pages
- Perfect for complex interactions with websites
- Use for research that requires navigating through multiple pages

STRATEGY:
1. Navigate directly to websites by typing URLs (e.g., "https://www.reddit.com")
2. Use screenshots to understand the page content
3. Click on elements to interact with the page
4. Extract information from pages by reading content in screenshots

SELF-SUFFICIENCY PRINCIPLES:
1. Gather thorough information without requiring user refinement
2. Try diverse web navigation approaches
3. Change navigation strategies when initial attempts aren't productive
4. Extract the most relevant information from web pages
5. Only request user input as a last resort
            """,
            handoff_description="A specialized agent for direct website interaction via browser",
            tools=[ComputerTool(computer)],
            # Use computer-use-preview model when using ComputerTool
            model="computer-use-preview",
            model_settings=ModelSettings(truncation="auto"),
        )

async def create_search_agent():
    """Creates a search agent with web search capabilities."""
    # Create the agent with web search tool only
    return Agent(
        name="SearchAgent",
        instructions="""You are a web search expert specializing in finding information online.

CAPABILITIES:
- Formulate effective search queries
- Find relevant, up-to-date information from authoritative sources
- Summarize findings concisely
- Provide links to original sources

TOOLS AND USAGE:
WebSearchTool:
- Searches the web for information on a given query
- Returns search results with titles, descriptions, and URLs
- Use for finding documentation, tutorials, examples, and technical answers

STRATEGY:
1. Formulate clear and specific search queries
2. Evaluate search results for relevance and accuracy
3. Synthesize information from multiple sources
4. Provide concise summaries with links to sources

SELF-SUFFICIENCY PRINCIPLES:
1. Gather thorough information without requiring user refinement
2. Try diverse search queries to explore topics from multiple angles
3. Reformulate queries when initial searches aren't productive
4. Filter results to identify the most relevant information
5. Only request user input as a last resort
        """,
        handoff_description="A specialized agent for web searches and information gathering",
        tools=[WebSearchTool()],
    )

# Create placeholders for the agents
browser_agent = None
search_agent = None

# Create the supervisor agent with specialized agents as tools
async def create_supervisor_agent() -> Agent:
    """Creates the Supervisor agent that orchestrates specialized agents as tools."""
    # Create specialized web agents
    global browser_agent, search_agent
    browser_agent = await create_browser_agent()
    search_agent = await create_search_agent()
    
    return Agent(
        name="Supervisor",
        instructions="""You are a coding assistant that delegates specialized tasks to expert agents.

AVAILABLE AGENTS:
1. CodeAgent: For coding tasks (writing, debugging, explaining code)
   Tools: run_claude_code

2. FilesystemAgent: For file system operations and project organization
   Tools: run_shell_command (for directories, file operations, system queries)

3. SearchAgent: For searching the web for information
   Tools: WebSearchTool (for finding information through web searches)

4. BrowserAgent: For directly interacting with websites
   Tools: ComputerTool (for browser navigation, clicking, typing, etc.)

WORKFLOW:
1. PLANNING:
   - Analyze the request and create a step-by-step plan
   - Define success criteria and verification methods for each step
   - Assign appropriate specialized agents to each step

2. EXECUTION:
   - Execute steps sequentially by delegating to specialized agents
   - IMPORTANT: Never implement code changes yourself - always delegate to CodeAgent
   - Clearly explain to CodeAgent what changes are needed and let it handle implementation
   - For web information gathering, use SearchAgent with WebSearchTool
   - For direct website interaction, use BrowserAgent with ComputerTool
   - Verify each step's success before proceeding
   - Adjust approach or revise plan if a step fails

3. VERIFICATION:
   - Perform final verification of the entire task
   - Address any remaining issues
   - Continue iterating until all success criteria are met

SELF-SUFFICIENCY:
- Work autonomously without user intervention
- Use specialized agents to their full potential
- Try multiple approaches before asking for user help
- Access files through FilesystemAgent, not user requests
- Only request user help as a last resort with specific needs

Always provide practical, executable solutions and persist until successful.""",
        tools=[
            # Specialized agents as tools
            code_agent.as_tool(
                tool_name="code_agent",
                tool_description="Delegate coding tasks to a specialized code agent",
            ),
            filesystem_agent.as_tool(
                tool_name="filesystem_agent",
                tool_description="Delegate filesystem operations to a specialized filesystem agent",
            ),
            search_agent.as_tool(
                tool_name="search_agent",
                tool_description="Delegate web searches to a specialized search agent",
            ),
            browser_agent.as_tool(
                tool_name="browser_agent",
                tool_description="Delegate website interactions to a specialized browser agent",
            ),
        ],
    )

# Function to process streamed response
async def process_streamed_response(agent, input_items):
    # Create console for rich text rendering
    console = Console()

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
                print(f"\n{agent_name}: Calling tool")
                # Access the raw item if available
                if hasattr(item, 'raw_item'):
                    raw_item = item.raw_item
                    # Get tool type
                    if hasattr(raw_item, 'type'):
                        print(f"  Tool type: {raw_item.type}")
                    # Get tool name for function calls
                    if hasattr(raw_item, 'name'):
                        print(f"  Tool name: {raw_item.name}")
                    # Get arguments
                    if hasattr(raw_item, 'arguments'):
                        try:
                            args = json.loads(raw_item.arguments)
                            print(f"  Arguments: {json.dumps(args, indent=2)}")
                        except:
                            print(f"  Arguments: {raw_item.arguments}")

            elif item.type == "tool_call_output_item":
                print(f"\n{agent_name}: Tool call result:")
                # Format output
                try:
                    if isinstance(item.output, str) and (item.output.startswith('{') or item.output.startswith('[')):
                        parsed_output = json.loads(item.output)
                        print(json.dumps(parsed_output, indent=2))
                    else:
                        print(f"  {item.output}")
                except:
                    print(f"  {item.output}")

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
        print("Non-interactive terminal detected. Command history disabled.")
        return False
        
    try:
        # Try to use a persistent history file
        home_dir = os.path.expanduser("~")
        history_dir = os.path.join(home_dir, ".supervisor_history")
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(history_dir, exist_ok=True)
            histfile = os.path.join(history_dir, "history")
        except:
            # Fall back to a temporary file if we can't create the directory
            import tempfile
            with tempfile.NamedTemporaryFile(prefix="supervisor_history_", delete=False) as temp_file:
                histfile = temp_file.name
        
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
        
        print(f"Command history enabled using {readline_module} module")
        print(f"History file: {histfile}")
        return True
        
    except Exception as e:
        print(f"Warning: Readline functionality limited: {str(e)}")
        print("Command history will not be available for this session.")
        return False

# Main function to run the agent loop
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

async def main():
    # Setup readline for command history
    readline_available = setup_readline()
    
    try:
        # Create the supervisor agent (which will also create the web agent with browser)
        agent = await create_supervisor_agent()
        # Initialize conversation history
        input_items: List = []
    
        print("\nSupervisor Agent ready. Type your request or 'exit' to quit.")
        print("Use up/down arrow keys to navigate command history.") if readline_available else None
        print("SearchAgent is available for web searches.")
        print("BrowserAgent is available for direct website interactions.")
        
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
                            result = await process_streamed_response(agent, input_items)
    
                            # Update input items with the result for the next iteration
                            input_items = result.to_input_list()
                except Exception as e:
                    print(f"\nError processing input: {str(e)}")
                    continue
    
        except KeyboardInterrupt:
            print("\nExiting Supervisor Agent")
    finally:
        # Clean up browser resources
        print("Closing browser...")
        await browser_manager.close()
        print("Browser closed.")

# Run the supervisor agent when this file is executed
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting Supervisor Agent")
