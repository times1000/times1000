# times1000

times1000 is a project focused on amplifying human creativity through autonomous AI agents. By creating a system of specialized agents capable of performing extremely complex tasks with minimal human input, we aim to multiply human creative potential and productivity. These agents work collaboratively to handle technical challenges, research information, and interact with web applications, freeing humans to focus on higher-level creative thinking and innovation.

Remarkably, all code in this repository was written entirely by AI models (Claude and OpenAI) - no humans have directly edited this codebase. This serves as a powerful demonstration of autonomous AI capabilities and the potential for AI-human collaboration.

## Setup

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
python -m playwright install
```

### API Keys

This application requires an OpenAI API key to function. You need to set the `OPENAI_API_KEY` environment variable before running:

```bash
# Set your OpenAI API key (replace YOUR_API_KEY with your actual key)
export OPENAI_API_KEY=YOUR_API_KEY  # Linux/macOS
set OPENAI_API_KEY=YOUR_API_KEY     # Windows
```

You can also create a `.env` file in the project root with your API key:

```
OPENAI_API_KEY=YOUR_API_KEY
```

If you don't have an API key, you can get one from: https://platform.openai.com/api-keys

## Usage

```bash
# Run the application
python main.py

# Run with test to verify browser functionality
python main.py -t

# Run with initial prompt
python main.py -p "your prompt here"
```

## Core Agents

- **Supervisor**: Orchestrates tasks and delegates to specialized agents
- **Browser**: Handles web navigation and interaction through Playwright
- **Code**: Provides code generation and analysis capabilities
- **Filesystem**: Manages file operations and project organization
- **Search**: Performs web searches to gather information

## Future Vision

Our roadmap for times1000 includes:

- Running multiple agents in parallel, with the supervisor managing them as needed
- Minimal human interaction - the supervisor only engages humans as a last resort
- Each agent operating in its own Docker container, allowing complete control over its environment
- Self-improving capabilities - agents will be able to edit their own code through GitHub PRs back to the original repository
- Fully autonomous operation with agents collaborating to solve increasingly complex problems