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

## Codebase Improvement Plan

### Critical Fixes
1. SQL Injection Vulnerability - Replace string concatenation with parameterized queries
2. Hardcoded API Keys - Move to environment variables
3. Hardcoded Database Credentials - Use environment variables
4. Event Emitter Memory Leak Risk - Set appropriate max listeners
5. Memory Leak in Components - Properly clean up intervals and event listeners

### Secondary Issues
1. Implement Anthropic Integration or remove stub
2. Replace `any` types with proper TypeScript interfaces
3. Improve error handling messages (remove implementation details)
4. Clean up commented out code
5. Move schema migrations from runtime code
6. Add proper input validation
7. Remove unsafe type assertions
8. Add React error boundaries
9. Fix socket error handling
10. Improve event handling in React components