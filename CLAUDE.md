# OpenAI Agents Project Guidelines

## Instructions
- Use `playwright` to access websites
- Use `github` to manage github access
- Use `docker-compose` to manage services

## Development Workflow
- Always test scripts after creating or modifying them to check for errors
- Run modified scripts directly to verify they work as expected
- For browser functionality, ensure Playwright is installed: `python -m playwright install`

## Git Workflow
- Always commit changes after completing any task
- Push changes to GitHub after any major change
- Always pull from GitHub before starting new work
- Keep commit messages short and concise
- No approval needed for commits

## Environment Setup
- Create virtual environment: `python -m venv venv`
- Activate virtual environment: `source venv/bin/activate` (macOS/Linux) or `venv\Scripts\activate` (Windows)
- Install dependencies: `pip install -r requirements.txt`
- Install Playwright browsers: `python -m playwright install`
- Start the application: `python supervisor.py`
- Deactivate when done: `deactivate`

## Browser Computer Setup
- The WebAgent now includes browser computer capabilities
- Uses Playwright to control a Chrome browser instance
- Install Playwright browsers: `python -m playwright install`
- The browser can perform operations like navigating, clicking, and typing
