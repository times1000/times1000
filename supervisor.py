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
import readline
import atexit
from typing import Optional, List

from agents import Agent, Runner, WebSearchTool, ItemHelpers, MessageOutputItem
from agents import ToolCallItem, ToolCallOutputItem, function_tool, trace

from rich.markdown import Markdown
from rich.console import Console

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

web_agent = Agent(
    name="WebAgent",
    instructions="""You are a web search expert specializing in finding information online.

When searching for information:
1. Formulate effective search queries
2. Find relevant, up-to-date information from authoritative sources
3. Summarize findings concisely
4. Provide links to original sources

TOOLS AND USAGE:
WebSearchTool:
- Searches the web for information on a given query
- Returns search results with titles, descriptions, and URLs
- Use for finding documentation, tutorials, examples, and technical answers

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

# Create the supervisor agent with specialized agents as tools
def create_supervisor_agent() -> Agent:
    """Creates the Supervisor agent that orchestrates specialized agents as tools."""
    return Agent(
        name="Supervisor",
        instructions="""You are a coding assistant that delegates specialized tasks to expert agents.

AVAILABLE AGENTS:
1. CodeAgent: For coding tasks (writing, debugging, explaining code)
   Tools: run_claude_code

2. FilesystemAgent: For file system operations and project organization
   Tools: run_shell_command (for directories, file operations, system queries)

3. WebAgent: For searching the web and finding information
   Tools: WebSearchTool

WORKFLOW:
1. PLANNING:
   - Analyze the request and create a step-by-step plan
   - Define success criteria and verification methods for each step
   - Assign appropriate specialized agents to each step

2. EXECUTION:
   - Execute steps sequentially by delegating to specialized agents
   - IMPORTANT: Never implement code changes yourself - always delegate to CodeAgent
   - Clearly explain to CodeAgent what changes are needed and let it handle implementation
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
            web_agent.as_tool(
                tool_name="web_agent",
                tool_description="Delegate web searches to a specialized web search agent",
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
    # Skip readline setup if we're in an environment that doesn't support it well
    if not sys.stdin.isatty():
        print("Non-interactive terminal detected. Command history disabled.")
        return False
        
    try:
        # Test if we can use readline effectively
        readline.get_current_history_length()
        
        # Try to use a temporary file for history
        import tempfile
        with tempfile.NamedTemporaryFile(prefix="supervisor_history_", delete=False) as temp_file:
            histfile = temp_file.name
        
        # Set history length
        readline.set_history_length(1000)
        
        # Save history on exit
        atexit.register(readline.write_history_file, histfile)
        
        # Enable arrow key navigation 
        readline.parse_and_bind("tab: complete")
        if sys.platform != 'win32':
            # These bindings work on Unix-like systems - using raw strings for escape sequences
            readline.parse_and_bind(r'"\e[A": previous-history')  # Up arrow
            readline.parse_and_bind(r'"\e[B": next-history')      # Down arrow
            
        print(f"Command history enabled (temporary file)")
        return True
    except Exception as e:
        print(f"Warning: Readline functionality limited: {str(e)}")
        print("Command history will not be available for this session.")
        return False

# Main function to run the agent loop
def safe_input(prompt):
    """Safely get input even if readline isn't working properly."""
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
    
    agent = create_supervisor_agent()
    # Initialize conversation history
    input_items: List = []

    try:
        print("\nSupervisor Agent ready. Type your request or 'exit' to quit.")
        
        while True:
            try:
                # Use appropriate input method
                user_input = safe_input("\n> ")
                
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

# Run the supervisor agent when this file is executed
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting Supervisor Agent")
