# OpenAI Agents Project Guidelines

## Instructions
- Use `playwright` to access websites
- Use `github` to manage github access
- Use `docker-compose` to manage services

## Development Workflow
- Always test scripts after creating or modifying them to check for errors
- Run modified scripts directly to verify they work as expected
- For browser functionality, ensure Playwright is installed: `python -m playwright install`
- After any code changes, ALWAYS:
  1. Run `python supervisor.py -t` to verify the browser agent works correctly
  2. Commit changes with clear descriptive messages
  3. Push changes to GitHub

## Git Workflow
- ALWAYS commit changes after completing any task or making file changes
- ALWAYS push to GitHub after any commits
- Always pull from GitHub before starting new work
- Keep commit messages descriptive yet concise
- No approval needed for commits

## Environment Setup
- Create virtual environment: `python -m venv venv`
- Activate virtual environment: `source venv/bin/activate` (macOS/Linux) or `venv\Scripts\activate` (Windows)
- Install dependencies: `pip install -r requirements.txt`
- Install Playwright browsers: `python -m playwright install`
- Start the application: `python supervisor.py`
- Deactivate when done: `deactivate`

## Running the Supervisor
- Basic usage: `python supervisor.py`
- Run with a test to verify browser functionality: `python supervisor.py -t`
- Run with an initial prompt: `python supervisor.py -p "your prompt here"`
- The browser only initializes when needed (lazy loading)

## Web Agents Setup
- Two separate agents for web interactions:
  1. SearchAgent: Uses WebSearchTool for finding information online
  2. BrowserAgent: Uses ComputerTool with Playwright for direct website interaction
- Install Playwright browsers: `python -m playwright install`
- The BrowserAgent can perform operations like navigating, clicking, and typing
- Direct URL navigation: BrowserAgent uses `await computer.navigate("https://example.com")`
- The browser starts with a blank page and only initializes when first needed
- The SearchAgent can perform web searches for information gathering

## Agent Selection Guidelines
- For information lookup: Use SearchAgent
- For interacting with websites: Use BrowserAgent
- Don't use both agents in the same task (model compatibility issue)
