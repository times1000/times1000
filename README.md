# Supervisor Agent

This repository contains a Supervisor Agent that orchestrates specialized agents for development tasks using the OpenAI Agents SDK and Claude Code CLI.

## Prerequisites

1. Set up a Python virtual environment:
   ```bash
   # Create a virtual environment
   python -m venv venv
   
   # Activate the virtual environment
   # On macOS/Linux:
   source venv/bin/activate
   # On Windows:
   # venv\Scripts\activate
   
   # Your terminal prompt should now show (venv) indicating the virtual environment is active
   ```

2. Install required Python packages:
   ```bash
   # Make sure your virtual environment is activated
   pip install -r requirements.txt
   
   # Install Playwright browsers
   python -m playwright install
   ```

3. Install Claude Code CLI:
   ```bash
   # Follow installation instructions at https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview
   ```

4. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

5. Deactivating the virtual environment when finished:
   ```bash
   deactivate
   ```

## Supervisor Agent

The Supervisor Agent delegates tasks to specialized agents based on their expertise. It follows a structured workflow of planning, execution, and verification.

### Running the Agent

```bash
# Basic usage
python supervisor.py

# Run with a test to verify browser functionality
python supervisor.py -t

# Run with an initial prompt
python supervisor.py -p "your prompt here"
```

This will start an interactive session where you can enter requests and get responses. Command history is available using the up/down arrow keys. Press Ctrl+C to exit.

The browser is lazy-loaded, meaning it only initializes when browser functionality is actually requested, improving startup performance.

## Architecture

The system uses an "agents-as-tools" pattern with four specialized agents:

1. **CodeAgent**: Handles code writing, debugging, and explanation tasks
   - Uses Claude CLI for code generation and analysis

2. **FilesystemAgent**: Manages file operations and project organization
   - Executes shell commands for file manipulation

3. **SearchAgent**: Performs web searches for information gathering
   - Uses WebSearchTool for online research

4. **BrowserAgent**: Directly interacts with websites via browser automation
   - Uses NavigateTool for page navigation with content extraction
   - Provides get_page_content tool for retrieving content from current page
   - Uses ComputerTool for advanced interactions (clicking, typing, etc.)

The Supervisor coordinates these agents by:
- Creating detailed step-by-step plans
- Delegating tasks to appropriate specialized agents
- Verifying the success of each step
- Iterating until all success criteria are met

## Features

- Command history with up/down arrow navigation
- Streaming responses with markdown rendering
- Structured planning and verification workflow
- Self-sufficiency with minimal user intervention
- Specialized agents for different domains
- Lazy-loaded browser automation with Playwright
- Advanced web content extraction in multiple formats (text, HTML, markdown)
- Browser page content retrieval without renavigation

## How to Extend

You can extend the system by:

1. Adding new specialized agents for different domains
2. Implementing additional tools for existing agents
3. Enhancing the supervisor's planning and verification capabilities

For more information, see the [OpenAI Agents SDK documentation](https://openai.github.io/openai-agents-python/) and [Claude Code documentation](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview)