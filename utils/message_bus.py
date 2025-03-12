"""
message_bus.py - Message bus for inter-agent communication
"""

import asyncio
import json
import uuid
import logging
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Any, Optional, Set, Callable, Awaitable, TypeVar, Generic

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MessageBus")

# Type variable for generic message payload
T = TypeVar('T')

class MessagePriority(Enum):
    """Message priority levels"""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3

class MessageType(Enum):
    """Message types for different communication patterns"""
    COMMAND = "command"  # Direct instruction to an agent
    QUERY = "query"      # Request for information
    RESPONSE = "response"  # Response to a query
    EVENT = "event"      # Notification of an occurrence
    BROADCAST = "broadcast"  # Message to all agents
    HEARTBEAT = "heartbeat"  # System health check

@dataclass
class Message(Generic[T]):
    """Message for inter-agent communication"""
    # Core message fields
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.EVENT
    priority: MessagePriority = MessagePriority.MEDIUM
    sender: str = ""
    recipients: List[str] = field(default_factory=list)
    topic: str = ""
    timestamp: float = field(default_factory=time.time)
    
    # Message content
    subject: str = ""
    payload: Optional[T] = None
    
    # Message flow control
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None
    expires_at: Optional[float] = None
    
    # Message routing
    routing_key: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        result = asdict(self)
        # Convert enum values to strings
        result["message_type"] = self.message_type.value
        result["priority"] = self.priority.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary"""
        # Convert string values to enums
        if "message_type" in data:
            data["message_type"] = MessageType(data["message_type"])
        if "priority" in data:
            data["priority"] = MessagePriority(data["priority"])
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if message has expired"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

class MessageBus:
    """Central message bus for agent communication"""
    
    def __init__(self, name: str = "main"):
        """Initialize the message bus"""
        self.name = name
        self.topics: Dict[str, Set[str]] = {}  # topic -> set of subscriber IDs
        self.subscribers: Dict[str, Dict[str, Callable[[Message], Awaitable[None]]]] = {}  # subscriber ID -> {topic -> handler}
        self.message_history: List[Message] = []
        self.max_history = 1000
        self._lock = asyncio.Lock()
    
    async def subscribe(self, 
                  subscriber_id: str, 
                  topics: List[str], 
                  handler: Callable[[Message], Awaitable[None]]) -> None:
        """
        Subscribe to topics
        
        Args:
            subscriber_id: Unique ID for the subscriber
            topics: List of topics to subscribe to
            handler: Async function to handle messages
        """
        async with self._lock:
            # Initialize subscriber if not exists
            if subscriber_id not in self.subscribers:
                self.subscribers[subscriber_id] = {}
            
            # Add handler for each topic
            for topic in topics:
                # Add topic if not exists
                if topic not in self.topics:
                    self.topics[topic] = set()
                
                # Add subscriber to topic
                self.topics[topic].add(subscriber_id)
                
                # Add handler for topic
                self.subscribers[subscriber_id][topic] = handler
    
    async def unsubscribe(self, subscriber_id: str, topics: Optional[List[str]] = None) -> None:
        """
        Unsubscribe from topics
        
        Args:
            subscriber_id: Unique ID for the subscriber
            topics: List of topics to unsubscribe from, if None unsubscribe from all
        """
        async with self._lock:
            if subscriber_id not in self.subscribers:
                return
            
            # If topics not specified, unsubscribe from all
            if topics is None:
                topics = list(self.subscribers[subscriber_id].keys())
            
            # Remove subscriber from each topic
            for topic in topics:
                if topic in self.subscribers[subscriber_id]:
                    del self.subscribers[subscriber_id][topic]
                
                if topic in self.topics and subscriber_id in self.topics[topic]:
                    self.topics[topic].remove(subscriber_id)
            
            # Remove subscriber if no topics left
            if not self.subscribers[subscriber_id]:
                del self.subscribers[subscriber_id]
    
    async def publish(self, message: Message) -> None:
        """
        Publish a message to the bus
        
        Args:
            message: Message to publish
        """
        # Check if message has expired
        if message.is_expired():
            logger.warning(f"Message {message.message_id} has expired, not publishing")
            return
        
        # Determine recipients
        recipients = []
        
        if message.recipients:
            # Direct message to specific recipients
            recipients = message.recipients
        elif message.topic:
            # Topic-based message
            async with self._lock:
                if message.topic in self.topics:
                    recipients = list(self.topics[message.topic])
        
        # No recipients, broadcast if it's a broadcast message
        if not recipients and message.message_type == MessageType.BROADCAST:
            async with self._lock:
                recipients = list(self.subscribers.keys())
        
        # Add to history
        await self._add_to_history(message)
        
        # Deliver to recipients
        delivery_tasks = []
        for recipient in recipients:
            delivery_tasks.append(self._deliver_message(recipient, message))
        
        # Wait for all deliveries to complete
        if delivery_tasks:
            await asyncio.gather(*delivery_tasks)
    
    async def request(self, 
                message: Message, 
                timeout: float = 10.0) -> Optional[Message]:
        """
        Send a request message and wait for response
        
        Args:
            message: Request message (should be of type QUERY)
            timeout: Timeout in seconds
            
        Returns:
            Response message or None if timeout
        """
        # Set message type to QUERY if not already
        if message.message_type != MessageType.QUERY:
            message.message_type = MessageType.QUERY
        
        # Create response future
        response_future = asyncio.Future()
        
        # Set up temporary subscriber for response
        async def response_handler(response: Message) -> None:
            if not response_future.done():
                response_future.set_result(response)
        
        # Subscribe to response topic
        response_topic = f"response.{message.message_id}"
        temp_subscriber_id = f"temp.{uuid.uuid4()}"
        
        await self.subscribe(temp_subscriber_id, [response_topic], response_handler)
        
        try:
            # Set reply_to field
            message.reply_to = response_topic
            
            # Publish request
            await self.publish(message)
            
            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(response_future, timeout)
                return response
            except asyncio.TimeoutError:
                logger.warning(f"Request {message.message_id} timed out")
                return None
        finally:
            # Unsubscribe temporary subscriber
            await self.unsubscribe(temp_subscriber_id)
    
    async def _deliver_message(self, recipient_id: str, message: Message) -> None:
        """Deliver message to a recipient"""
        async with self._lock:
            if recipient_id not in self.subscribers:
                return
            
            # Find handler based on topic
            handler = None
            if message.topic and message.topic in self.subscribers[recipient_id]:
                handler = self.subscribers[recipient_id][message.topic]
            
            # If no handler for topic, try wildcard handler
            if handler is None and "*" in self.subscribers[recipient_id]:
                handler = self.subscribers[recipient_id]["*"]
        
        # Deliver message if handler found
        if handler:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Error delivering message to {recipient_id}: {e}")
    
    async def _add_to_history(self, message: Message) -> None:
        """Add message to history"""
        async with self._lock:
            self.message_history.append(message)
            
            # Trim history if needed
            if len(self.message_history) > self.max_history:
                self.message_history = self.message_history[-self.max_history:]
    
    async def get_history(self, 
                    topic: Optional[str] = None, 
                    sender: Optional[str] = None,
                    message_type: Optional[MessageType] = None,
                    limit: int = 100) -> List[Message]:
        """
        Get message history with optional filtering
        
        Args:
            topic: Filter by topic
            sender: Filter by sender
            message_type: Filter by message type
            limit: Maximum number of messages to return
            
        Returns:
            List of messages matching filters
        """
        async with self._lock:
            # Apply filters
            filtered = self.message_history
            
            if topic:
                filtered = [m for m in filtered if m.topic == topic]
            
            if sender:
                filtered = [m for m in filtered if m.sender == sender]
            
            if message_type:
                filtered = [m for m in filtered if m.message_type == message_type]
            
            # Return limited number of most recent messages
            return sorted(filtered, key=lambda m: m.timestamp, reverse=True)[:limit]

# Singleton instance
_default_bus = None

def get_default_bus() -> MessageBus:
    """Get the default message bus instance"""
    global _default_bus
    if _default_bus is None:
        _default_bus = MessageBus()
    return _default_bus

# Helper functions for common message patterns
async def broadcast_event(topic: str, subject: str, payload: Any = None, sender: str = "system") -> None:
    """
    Broadcast an event to all subscribers
    
    Args:
        topic: Message topic
        subject: Event subject
        payload: Event payload
        sender: Event sender
    """
    bus = get_default_bus()
    message = Message(
        message_type=MessageType.BROADCAST,
        sender=sender,
        topic=topic,
        subject=subject,
        payload=payload
    )
    await bus.publish(message)

async def send_command(recipient: str, 
                 command: str, 
                 payload: Any = None, 
                 sender: str = "system",
                 priority: MessagePriority = MessagePriority.MEDIUM) -> None:
    """
    Send a command to a specific agent
    
    Args:
        recipient: Agent to receive the command
        command: Command to execute
        payload: Command parameters
        sender: Command sender
        priority: Command priority
    """
    bus = get_default_bus()
    message = Message(
        message_type=MessageType.COMMAND,
        sender=sender,
        recipients=[recipient],
        subject=command,
        payload=payload,
        priority=priority
    )
    await bus.publish(message)

async def query_agent(recipient: str, 
                query: str, 
                payload: Any = None, 
                sender: str = "system",
                timeout: float = 3.0) -> Optional[Message]:
    """
    Query an agent and wait for response
    
    Args:
        recipient: Agent to query
        query: Query string
        payload: Query parameters
        sender: Query sender
        timeout: Timeout in seconds (default reduced to 3s for tests)
        
    Returns:
        Response message or None if timeout
    """
    bus = get_default_bus()
    message = Message(
        message_type=MessageType.QUERY,
        sender=sender,
        recipients=[recipient],
        subject=query,
        payload=payload
    )
    return await bus.request(message, timeout)