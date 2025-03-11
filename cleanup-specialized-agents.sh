#!/bin/bash
# Script to remove specialized agent files after migrating to unified agent architecture

echo "Cleaning up specialized agent files..."

# Remove specialized agent implementations
echo "Removing specialized agent implementations..."
rm -f src/agents/ContentAnalyzerAgent.ts
rm -f src/agents/CodeAssistantAgent.ts
rm -f src/agents/SocialMediaAgent.ts
rm -f src/core/agents/BaseAgent.ts
rm -f src/core/agents/ContentAnalyzerAgent.ts
rm -f src/core/agents/CodeAssistantAgent.ts
rm -f src/core/agents/SocialMediaAgent.ts
rm -f src/core/agents/AgentFactory.ts

# Try to remove the directories if they're empty
rmdir src/agents 2>/dev/null
rmdir src/core/agents 2>/dev/null

echo "Cleanup complete!"
echo "Note: You may need to update any import references in your front-end code."
echo "Unified agent implementation is now available in src/core/Agent.ts"