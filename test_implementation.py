"""
test_implementation.py - Simple test script to demonstrate the implemented components
"""

import asyncio
import logging
import os
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TestImplementation")

# Import our components
from utils.message_bus import (
    MessageBus, Message, MessageType, MessagePriority,
    broadcast_event, send_command, query_agent
)
from utils.knowledge_repository import (
    KnowledgeRepository, KnowledgeItem, KnowledgeType,
    store_fact, store_user_preference, find_knowledge
)
# Conditionally import GitHub integration (only needed for GitHub tests)
try:
    from utils.github_integration import (
        GitHubClient, suggest_code_improvement
    )
    github_available = True
except ImportError:
    github_available = False
    print("GitHub integration not available - skipping those tests")

# Create test agent message handler
async def agent_message_handler(agent_id: str, message: Message) -> None:
    """Message handler for test agents"""
    logger.info(f"Agent {agent_id} received message: {message.subject}")
    
    # If it's a query, send a response
    if message.message_type == MessageType.QUERY and message.reply_to:
        # Create response message
        response = Message(
            message_type=MessageType.RESPONSE,
            sender=agent_id,
            recipients=[message.sender],
            topic=message.reply_to,
            subject=f"Response to: {message.subject}",
            payload=f"This is a response from {agent_id} to query: {message.subject}",
            correlation_id=message.message_id
        )
        
        # Get the bus
        bus = MessageBus()
        
        # Send response
        await bus.publish(response)

async def test_message_bus():
    """Test the message bus functionality"""
    logger.info("Testing message bus...")
    
    # Create message bus
    bus = MessageBus()
    
    # Create test agents
    agents = ["agent1", "agent2", "agent3"]
    
    # Subscribe agents to topics
    for agent_id in agents:
        # We need to create a proper async wrapper for the handler
        async def create_handler(agent_id):
            async def handler(message):
                await agent_message_handler(agent_id, message)
            return handler
            
        handler = await create_handler(agent_id)
        await bus.subscribe(agent_id, ["test", "commands", "notifications"], handler)
    
    # Broadcast an event
    logger.info("Broadcasting event...")
    await broadcast_event(
        topic="notifications",
        subject="System notification",
        payload="This is a test notification",
        sender="system"
    )
    
    # Send a command to a specific agent
    logger.info("Sending command...")
    await send_command(
        recipient="agent1",
        command="Execute test",
        payload={"param1": "value1", "param2": "value2"},
        sender="system",
        priority=MessagePriority.HIGH
    )
    
    # Query an agent
    logger.info("Querying agent...")
    response = await query_agent(
        recipient="agent2",
        query="What is your status?",
        sender="system",
        timeout=5.0
    )
    
    if response:
        logger.info(f"Got response: {response.payload}")
    else:
        logger.warning("No response received")
    
    # Clean up
    for agent_id in agents:
        await bus.unsubscribe(agent_id)
    
    logger.info("Message bus test completed")

async def test_knowledge_repository():
    """Test the knowledge repository functionality"""
    logger.info("Testing knowledge repository...")
    
    # Create memory-only repository for testing
    repo = KnowledgeRepository()
    
    # Add some knowledge items
    logger.info("Adding knowledge items...")
    fact_id = await store_fact(
        title="Python is dynamically typed",
        content="Python is a dynamically typed language, which means type checking is performed at runtime.",
        confidence=0.95,
        tags=["python", "programming", "types"]
    )
    
    pref_id = await store_user_preference(
        title="Preferred editor",
        content="VS Code",
        tags=["tools", "preferences"]
    )
    
    # Create a more complex item
    code_item = KnowledgeItem(
        knowledge_type=KnowledgeType.CODE,
        title="Example Python function",
        content="""def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n-1)""",
        tags=["python", "code", "algorithm"],
        categories=["examples", "algorithms"],
        confidence=1.0
    )
    code_id = await repo.add_item(code_item)
    
    # Search for items
    logger.info("Searching for 'python'...")
    python_items = await repo.search(query="python")
    logger.info(f"Found {len(python_items)} items:")
    for item in python_items:
        logger.info(f"- {item.title} ({item.knowledge_type.value})")
    
    # Update an item
    logger.info("Updating item...")
    updated_id = await repo.update_item(
        item_id=code_id,
        content="""def factorial(n):
    # Improved version with error checking
    if not isinstance(n, int) or n < 0:
        raise ValueError("Input must be a non-negative integer")
    if n <= 1:
        return 1
    return n * factorial(n-1)"""
    )
    
    # Get the updated item
    if updated_id:
        updated_item = await repo.get_item(updated_id)
        logger.info(f"Updated item: {updated_item.title} (version {updated_item.version})")
    
    # Get version history
    logger.info("Getting version history...")
    versions = await repo.get_version_history(code_id)
    logger.info(f"Found {len(versions)} versions")
    
    logger.info("Knowledge repository test completed")

async def main():
    """Run all tests"""
    # Test message bus
    await test_message_bus()
    
    # Test knowledge repository
    await test_knowledge_repository()
    
    # Note: We're not testing GitHub integration as it requires an actual token
    logger.info("All tests completed")

if __name__ == "__main__":
    asyncio.run(main())