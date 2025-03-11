FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Explicitly install Anthropic SDK
RUN npm install @anthropic-ai/sdk@latest

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Install additional tools for code execution
RUN apk add --no-cache python3 py3-pip curl git

# Create directory for generated code
RUN mkdir -p /app/generated-code && chmod 777 /app/generated-code

# Expose the port
EXPOSE 3000

# Don't build in Dockerfile - we'll build in the container with volume mounting
# Command to run the app in development mode with hot reloading
CMD ["npm", "run", "dev"]