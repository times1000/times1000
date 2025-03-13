"""
Utility modules for the Times1000 project
"""

import logging
import time
import random
import asyncio
from typing import Callable, Any, Dict, List, Optional, TypeVar, Generic, Union, Tuple
from enum import Enum
from dataclasses import dataclass
from functools import wraps
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("utils")

# Type variable for generic return type
T = TypeVar('T')

class ConfidenceLevel(Enum):
    """Confidence levels for agent decisions and actions"""
    HIGH = "high"
    MEDIUM = "medium" 
    LOW = "low"
    UNKNOWN = "unknown"

class ErrorCategory(Enum):
    """Categories of errors that can occur during agent operations"""
    NETWORK = "network"
    TIMEOUT = "timeout"
    PERMISSION = "permission"
    NOT_FOUND = "not_found"
    VALIDATION = "validation"
    SYNTAX = "syntax"
    LOGIC = "logic"
    API = "api"
    UNKNOWN = "unknown"

@dataclass
class AgentResult(Generic[T]):
    """Result object returned by agent operations with error handling"""
    success: bool
    value: Optional[T] = None
    error_message: Optional[str] = None
    error_category: Optional[ErrorCategory] = None
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    retry_count: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize metadata dict if not provided"""
        if self.metadata is None:
            self.metadata = {}
    
    @classmethod
    def success_result(cls, value: T, confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM) -> 'AgentResult[T]':
        """Create a successful result"""
        return cls(
            success=True,
            value=value,
            confidence=confidence,
            metadata={}
        )
    
    @classmethod
    def error_result(cls, 
                    error_message: str, 
                    error_category: ErrorCategory = ErrorCategory.UNKNOWN,
                    retry_count: int = 0) -> 'AgentResult[T]':
        """Create an error result"""
        return cls(
            success=False,
            error_message=error_message,
            error_category=error_category,
            retry_count=retry_count,
            metadata={}
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization"""
        return {
            "success": self.success,
            "value": self.value,
            "error_message": self.error_message,
            "error_category": self.error_category.value if self.error_category else None,
            "confidence": self.confidence.value if self.confidence else ConfidenceLevel.UNKNOWN.value,
            "retry_count": self.retry_count,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentResult[Any]':
        """Create result from dictionary"""
        return cls(
            success=data.get("success", False),
            value=data.get("value"),
            error_message=data.get("error_message"),
            error_category=ErrorCategory(data.get("error_category")) if data.get("error_category") else None,
            confidence=ConfidenceLevel(data.get("confidence", "unknown")),
            retry_count=data.get("retry_count", 0),
            metadata=data.get("metadata", {})
        )

class RetryStrategy(Enum):
    """Retry strategies for failed operations"""
    NONE = "none"
    IMMEDIATE = "immediate"
    LINEAR_BACKOFF = "linear_backoff"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    RANDOM_BACKOFF = "random_backoff"

async def retry_async(
    func: Callable[..., Any],
    max_retries: int = 3,
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    error_categories: List[ErrorCategory] = None
) -> AgentResult:
    """
    Retry an async function with configurable retry strategy
    
    Args:
        func: The async function to retry
        max_retries: Maximum number of retries
        retry_strategy: The retry strategy to use
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        error_categories: List of error categories to retry, None means retry all
        
    Returns:
        AgentResult with the function result or error information
    """
    retry_count = 0
    
    while True:
        try:
            result = await func()
            
            # If the result is already an AgentResult, update retry count and return
            if isinstance(result, AgentResult):
                result.retry_count = retry_count
                return result
                
            # Otherwise wrap the result in a success AgentResult
            return AgentResult.success_result(result)
            
        except Exception as e:
            retry_count += 1
            error_message = str(e)
            error_category = determine_error_category(e)
            
            # Log the error
            logger.warning(f"Error in retry_async (attempt {retry_count}/{max_retries}): {error_message}")
            
            # Check if we should retry based on error category
            if error_categories and error_category not in error_categories:
                return AgentResult.error_result(
                    error_message=error_message,
                    error_category=error_category,
                    retry_count=retry_count
                )
            
            # Check if we've reached max retries
            if retry_count >= max_retries:
                return AgentResult.error_result(
                    error_message=error_message,
                    error_category=error_category,
                    retry_count=retry_count
                )
            
            # Calculate delay based on retry strategy
            delay = calculate_retry_delay(
                retry_strategy, 
                retry_count, 
                base_delay, 
                max_delay
            )
            
            # Log the retry attempt
            logger.info(f"Retrying in {delay:.2f} seconds (strategy: {retry_strategy.value})")
            
            # Wait before retry
            await asyncio.sleep(delay)

def determine_error_category(exception: Exception) -> ErrorCategory:
    """
    Determine the error category based on the exception
    
    Args:
        exception: The exception to categorize
        
    Returns:
        ErrorCategory enum value
    """
    error_type = type(exception).__name__
    error_message = str(exception).lower()
    
    # Network errors
    if any(key in error_type.lower() for key in ["connection", "network", "http", "socket", "timeout"]):
        return ErrorCategory.NETWORK
        
    # Timeout errors
    if "timeout" in error_type.lower() or "timeout" in error_message:
        return ErrorCategory.TIMEOUT
        
    # Permission errors
    if any(key in error_message for key in ["permission", "access", "forbidden", "unauthorized"]):
        return ErrorCategory.PERMISSION
        
    # Not found errors
    if "not found" in error_message or "404" in error_message:
        return ErrorCategory.NOT_FOUND
        
    # Validation errors
    if any(key in error_message for key in ["invalid", "validation", "format", "schema"]):
        return ErrorCategory.VALIDATION
        
    # Syntax errors
    if isinstance(exception, (SyntaxError, TypeError)):
        return ErrorCategory.SYNTAX
        
    # API errors
    if "api" in error_message:
        return ErrorCategory.API
        
    # Default to unknown
    return ErrorCategory.UNKNOWN

def calculate_retry_delay(
    strategy: RetryStrategy,
    retry_count: int,
    base_delay: float,
    max_delay: float
) -> float:
    """
    Calculate the delay before next retry based on the strategy
    
    Args:
        strategy: The retry strategy to use
        retry_count: Current retry attempt (1-based)
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        
    Returns:
        Delay in seconds before next retry
    """
    if strategy == RetryStrategy.NONE or strategy == RetryStrategy.IMMEDIATE:
        return 0
        
    if strategy == RetryStrategy.LINEAR_BACKOFF:
        delay = base_delay * retry_count
        
    elif strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
        delay = base_delay * (2 ** (retry_count - 1))
        
    elif strategy == RetryStrategy.RANDOM_BACKOFF:
        # Random delay between base_delay and base_delay * 3 * retry_count
        max_rand = base_delay * 3 * retry_count
        delay = base_delay + random.random() * (max_rand - base_delay)
        
    else:
        # Default to immediate retry
        return 0
    
    # Ensure we don't exceed max_delay
    return min(delay, max_delay)

@dataclass
class NavigationHistoryEntry:
    """A single entry in the browser navigation history"""
    url: str
    timestamp: datetime
    title: Optional[str] = None
    status_code: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the entry to a dictionary"""
        return {
            "url": self.url,
            "timestamp": self.timestamp.isoformat(),
            "title": self.title,
            "status_code": self.status_code,
            "success": self.success,
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NavigationHistoryEntry':
        """Create an entry from a dictionary"""
        return cls(
            url=data.get("url", ""),
            timestamp=datetime.fromisoformat(data.get("timestamp")) if data.get("timestamp") else datetime.now(),
            title=data.get("title"),
            status_code=data.get("status_code"),
            success=data.get("success", True),
            error_message=data.get("error_message")
        )

@dataclass
class BrowserSessionContext:
    """Context for maintaining state between browser interactions"""
    user_id: str = ""
    visited_urls: List[str] = None
    navigation_history: List[NavigationHistoryEntry] = None
    session_data: Dict[str, Any] = None
    cookies: Dict[str, Dict[str, Any]] = None
    headers: Dict[str, str] = None
    current_url: Optional[str] = None
    
    def __post_init__(self):
        """Initialize lists and dicts if not provided"""
        if self.visited_urls is None:
            self.visited_urls = []
        if self.navigation_history is None:
            self.navigation_history = []
        if self.session_data is None:
            self.session_data = {}
        if self.cookies is None:
            self.cookies = {}
        if self.headers is None:
            self.headers = {}
    
    def add_navigation_entry(self, url: str, title: Optional[str] = None, 
                           status_code: Optional[int] = None, success: bool = True, 
                           error_message: Optional[str] = None) -> None:
        """Add a new entry to the navigation history"""
        entry = NavigationHistoryEntry(
            url=url,
            timestamp=datetime.now(),
            title=title,
            status_code=status_code,
            success=success,
            error_message=error_message
        )
        
        self.navigation_history.append(entry)
        
        # Add to visited URLs if successful and not already in the list
        if success and url not in self.visited_urls:
            self.visited_urls.append(url)
            
        # Update current URL
        if success:
            self.current_url = url
    
    def add_cookies(self, domain: str, cookies: Dict[str, Any]) -> None:
        """Add cookies for a specific domain"""
        if domain not in self.cookies:
            self.cookies[domain] = {}
            
        # Update existing cookies
        self.cookies[domain].update(cookies)
    
    def get_cookies_for_domain(self, domain: str) -> Dict[str, Any]:
        """Get cookies for a specific domain"""
        return self.cookies.get(domain, {})
    
    def get_all_cookies(self) -> Dict[str, Dict[str, Any]]:
        """Get all cookies"""
        return self.cookies
    
    def clear_cookies(self) -> None:
        """Clear all cookies"""
        self.cookies = {}
    
    def set_header(self, name: str, value: str) -> None:
        """Set a header for future requests"""
        self.headers[name] = value
    
    def get_headers(self) -> Dict[str, str]:
        """Get all headers"""
        return self.headers
    
    def store_session_data(self, key: str, value: Any) -> None:
        """Store arbitrary session data"""
        self.session_data[key] = value
    
    def get_session_data(self, key: str, default: Any = None) -> Any:
        """Get session data by key"""
        return self.session_data.get(key, default)
    
    def get_last_visit(self) -> Optional[NavigationHistoryEntry]:
        """Get the most recent navigation history entry"""
        if not self.navigation_history:
            return None
        return self.navigation_history[-1]
    
    def get_previous_visit(self) -> Optional[NavigationHistoryEntry]:
        """Get the second most recent navigation history entry"""
        if len(self.navigation_history) < 2:
            return None
        return self.navigation_history[-2]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization"""
        return {
            "user_id": self.user_id,
            "visited_urls": self.visited_urls,
            "navigation_history": [entry.to_dict() for entry in self.navigation_history],
            "session_data": self.session_data,
            "cookies": self.cookies,
            "headers": self.headers,
            "current_url": self.current_url
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BrowserSessionContext':
        """Create context from dictionary"""
        context = cls(
            user_id=data.get("user_id", ""),
            visited_urls=data.get("visited_urls", []),
            navigation_history=[
                NavigationHistoryEntry.from_dict(entry) 
                for entry in data.get("navigation_history", [])
            ],
            session_data=data.get("session_data", {}),
            cookies=data.get("cookies", {}),
            headers=data.get("headers", {}),
            current_url=data.get("current_url")
        )
        return context

@dataclass
class AgentContextWrapper(Generic[T]):
    """Wrapper for maintaining context across agent calls"""
    agent_name: str
    agent_context: T  # Generic type for the context (e.g., BrowserSessionContext)
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize metadata dict if not provided"""
        if self.metadata is None:
            self.metadata = {}
    
    def update_metadata(self, key: str, value: Any) -> None:
        """Update metadata"""
        self.metadata[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert wrapper to dictionary for serialization"""
        context_dict = {}
        if hasattr(self.agent_context, 'to_dict'):
            context_dict = self.agent_context.to_dict()
        return {
            "agent_name": self.agent_name,
            "context": context_dict,
            "metadata": self.metadata
        }

def with_retry(
    max_retries: int = 3,
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    error_categories: List[ErrorCategory] = None
):
    """
    Decorator to add retry capability to async functions
    
    Args:
        max_retries: Maximum number of retries
        retry_strategy: The retry strategy to use
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        error_categories: List of error categories to retry, None means retry all
        
    Returns:
        Decorated function with retry capability
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async def wrapped_func():
                return await func(*args, **kwargs)
                
            return await retry_async(
                wrapped_func,
                max_retries=max_retries,
                retry_strategy=retry_strategy,
                base_delay=base_delay,
                max_delay=max_delay,
                error_categories=error_categories
            )
        return wrapper
    return decorator