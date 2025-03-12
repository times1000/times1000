#!/bin/bash

# run_containers.sh - Script to run the containerized agents

# Check if Docker is installed
if ! command -v docker &> /dev/null
then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null
then
    echo "Error: Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Set environment variables
export KNOWLEDGE_REPOSITORY_DIR="./shared/knowledge"

# Build the Docker images
echo "Building Docker images..."
docker-compose build

# Run the containers
echo "Starting containers..."
docker-compose up

# Handle cleanup on exit
cleanup() {
    echo "Stopping containers..."
    docker-compose down
}

# Set trap to clean up on exit
trap cleanup EXIT

# Wait for user input
read -p "Press enter to stop all containers..."