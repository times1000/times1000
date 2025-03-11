FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Expose the port
EXPOSE 3000

# Don't build in Dockerfile - we'll build in the container with volume mounting
# Command to run the app in development mode with hot reloading
CMD ["npm", "run", "dev"]