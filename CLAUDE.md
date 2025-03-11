# CLAUDE.md - AI Assistant Guide

## Build/Test Commands
- Build: `npm run build`
- Dev: `npm run dev`
- Lint: `npm run lint`
- Typecheck: `npm run typecheck`
- Test all: `npm test`
- Test single: `npm test -- -t "test name"`

## Code Style Guidelines
- Use TypeScript for type safety
- Format with Prettier, enforce with ESLint
- Use named exports over default exports
- Follow kebab-case for filenames, PascalCase for components
- Prefer functional components with React hooks
- Import order: React → external libs → internal modules → types/styles
- Error handling: Use try/catch with descriptive error messages
- Comments: Document "why" not "what" (code should be self-explanatory)
- Keep functions small and focused on a single responsibility

## Workflow Instructions
- Always run type check (`npm run typecheck`) after making code changes
- Fix ALL TypeScript errors after making changes, whether directly related to your changes or not
- Automatically commit changes to git after completing tasks
- Keep commit messages short and concise - no approval needed
- Push changes to the repository after committing