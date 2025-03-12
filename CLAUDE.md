# OpenAI Agents Project Guidelines

## Instructions
- Use `playwright` to access websites
- Use `github` to manage github access
- Use `docker-compose` to manage services

## Development Workflow
- ALWAYS thoroughly test scripts before commit or push
- Run modified scripts directly to verify they work as expected
- For browser functionality, ensure Playwright is installed: `python -m playwright install`
- After any code changes, the workflow MUST be:
  1. Run `python supervisor.py -t` to verify the browser agent works correctly
  2. Test all affected functionality thoroughly and completely
  3. Ensure ALL tests pass successfully before proceeding
  4. Commit changes with clear descriptive messages
  5. Push changes to GitHub
  6. Mark the task as complete only after successful tests, commit, and push

## Git Workflow
- NEVER commit code that has not been thoroughly tested
- ONLY commit changes after ALL tests pass successfully
- ALWAYS push to GitHub immediately after committing
- Always pull from GitHub before starting new work
- Keep commit messages descriptive and clear about what changed
- No approval needed for commits, but quality is your responsibility

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

## Testing Requirements
- ALL changes MUST be tested before commit and push
- Browser functionality testing:
  - Run `python supervisor.py -t` and confirm browser only initializes when needed
  - Verify navigation works by asking the agent to visit a specific URL
  - Ensure browser displays the requested content correctly
  - Test at least one interaction (click, scroll, etc.) if relevant
- Test changes in isolation first, then as part of the complete system
- If any test fails, fix the issue before committing
- Document any testing steps or issues in commit messages

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
