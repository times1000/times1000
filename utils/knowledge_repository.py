"""
knowledge_repository.py - Shared knowledge repository for agents
"""

import os
import json
import asyncio
import logging
import time
import uuid
from typing import Dict, List, Any, Optional, Set, TypeVar, Generic
from enum import Enum
from dataclasses import dataclass, field, asdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("KnowledgeRepository")

# Type variable for generic knowledge content
T = TypeVar('T')

class KnowledgeType(Enum):
    """Types of knowledge stored in the repository"""
    FACT = "fact"               # Verified information
    CONCEPT = "concept"         # Abstract idea or explanation
    PROCEDURE = "procedure"     # Step-by-step process
    CODE = "code"               # Code snippet or implementation
    PREFERENCE = "preference"   # User preference
    DECISION = "decision"       # Decision made by an agent
    REFERENCE = "reference"     # External reference (URL, document)
    OBSERVATION = "observation" # Observation from an agent
    OTHER = "other"             # Miscellaneous knowledge

@dataclass
class KnowledgeItem(Generic[T]):
    """Item of knowledge stored in the repository"""
    # Core fields
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    knowledge_type: KnowledgeType = KnowledgeType.FACT
    title: str = ""
    content: Optional[T] = None
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    created_by: str = "system"
    confidence: float = 1.0  # 0.0-1.0, how confident we are in this knowledge
    
    # Organization
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    
    # Versioning
    version: int = 1
    previous_version: Optional[str] = None
    
    # Relations
    related_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert knowledge item to dictionary"""
        result = asdict(self)
        # Convert enum values to strings
        result["knowledge_type"] = self.knowledge_type.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeItem':
        """Create knowledge item from dictionary"""
        # Convert string values to enums
        if "knowledge_type" in data:
            data["knowledge_type"] = KnowledgeType(data["knowledge_type"])
        return cls(**data)
    
    def update(self, 
          title: Optional[str] = None,
          content: Optional[Any] = None,
          tags: Optional[List[str]] = None,
          categories: Optional[List[str]] = None,
          confidence: Optional[float] = None,
          knowledge_type: Optional[KnowledgeType] = None) -> None:
        """Update knowledge item fields"""
        # Store current state as previous version
        self.previous_version = self.id
        self.id = str(uuid.uuid4())
        self.version += 1
        self.updated_at = time.time()
        
        # Update fields if provided
        if title is not None:
            self.title = title
        if content is not None:
            self.content = content
        if tags is not None:
            self.tags = tags
        if categories is not None:
            self.categories = categories
        if confidence is not None:
            self.confidence = confidence
        if knowledge_type is not None:
            self.knowledge_type = knowledge_type

class KnowledgeRepository:
    """Shared knowledge repository for storing and retrieving agent knowledge"""
    
    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize the knowledge repository
        
        Args:
            storage_dir: Directory for persistent storage, if None use in-memory only
        """
        self.items: Dict[str, KnowledgeItem] = {}
        self.storage_dir = storage_dir
        self.version_history: Dict[str, List[str]] = {}  # original_id -> list of version IDs
        self._lock = asyncio.Lock()
        
        # Create storage directory if provided
        if self.storage_dir:
            os.makedirs(self.storage_dir, exist_ok=True)
            self._load_from_disk()
    
    async def add_item(self, item: KnowledgeItem) -> str:
        """
        Add a new knowledge item
        
        Args:
            item: Knowledge item to add
            
        Returns:
            ID of the added item
        """
        async with self._lock:
            self.items[item.id] = item
            
            # Add to version history if it's a new version of an existing item
            if item.previous_version:
                if item.previous_version not in self.version_history:
                    self.version_history[item.previous_version] = []
                self.version_history[item.previous_version].append(item.id)
            
            # Save to disk if storage directory configured
            if self.storage_dir:
                self._save_to_disk()
            
            return item.id
    
    async def get_item(self, item_id: str) -> Optional[KnowledgeItem]:
        """
        Get a knowledge item by ID
        
        Args:
            item_id: ID of the item to get
            
        Returns:
            Knowledge item or None if not found
        """
        async with self._lock:
            return self.items.get(item_id)
    
    async def update_item(self, 
                    item_id: str, 
                    title: Optional[str] = None,
                    content: Optional[Any] = None,
                    tags: Optional[List[str]] = None,
                    categories: Optional[List[str]] = None,
                    confidence: Optional[float] = None,
                    knowledge_type: Optional[KnowledgeType] = None) -> Optional[str]:
        """
        Update an existing knowledge item
        
        Args:
            item_id: ID of the item to update
            title: New title
            content: New content
            tags: New tags
            categories: New categories
            confidence: New confidence
            knowledge_type: New knowledge type
            
        Returns:
            ID of the updated item (new version) or None if not found
        """
        async with self._lock:
            item = self.items.get(item_id)
            if item is None:
                return None
            
            # Create new version
            item.update(
                title=title,
                content=content,
                tags=tags,
                categories=categories,
                confidence=confidence,
                knowledge_type=knowledge_type
            )
            
            # Add new version
            self.items[item.id] = item
            
            # Update version history
            if item.previous_version not in self.version_history:
                self.version_history[item.previous_version] = []
            self.version_history[item.previous_version].append(item.id)
            
            # Save to disk if storage directory configured
            if self.storage_dir:
                self._save_to_disk()
            
            return item.id
    
    async def delete_item(self, item_id: str) -> bool:
        """
        Delete a knowledge item
        
        Args:
            item_id: ID of the item to delete
            
        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if item_id not in self.items:
                return False
            
            # Remove item
            del self.items[item_id]
            
            # Save to disk if storage directory configured
            if self.storage_dir:
                self._save_to_disk()
            
            return True
    
    async def search(self, 
               query: str = "", 
               tags: Optional[List[str]] = None,
               categories: Optional[List[str]] = None,
               knowledge_type: Optional[KnowledgeType] = None,
               confidence_threshold: float = 0.0,
               limit: int = 100) -> List[KnowledgeItem]:
        """
        Search for knowledge items
        
        Args:
            query: Text to search in title and content
            tags: Filter by tags
            categories: Filter by categories
            knowledge_type: Filter by knowledge type
            confidence_threshold: Minimum confidence level
            limit: Maximum number of items to return
            
        Returns:
            List of matching knowledge items
        """
        async with self._lock:
            # Start with all items
            results = list(self.items.values())
            
            # Filter by query
            if query:
                query = query.lower()
                filtered = []
                for item in results:
                    # Check title
                    if query in item.title.lower():
                        filtered.append(item)
                        continue
                    
                    # Check content (if it's a string)
                    if isinstance(item.content, str) and query in item.content.lower():
                        filtered.append(item)
                        continue
                    
                    # Check tags
                    if any(query in tag.lower() for tag in item.tags):
                        filtered.append(item)
                        continue
                    
                    # Check categories
                    if any(query in category.lower() for category in item.categories):
                        filtered.append(item)
                        continue
                
                results = filtered
            
            # Filter by tags
            if tags:
                results = [
                    item for item in results
                    if any(tag in item.tags for tag in tags)
                ]
            
            # Filter by categories
            if categories:
                results = [
                    item for item in results
                    if any(category in item.categories for category in categories)
                ]
            
            # Filter by knowledge type
            if knowledge_type:
                results = [
                    item for item in results
                    if item.knowledge_type == knowledge_type
                ]
            
            # Filter by confidence
            if confidence_threshold > 0:
                results = [
                    item for item in results
                    if item.confidence >= confidence_threshold
                ]
            
            # Sort by confidence (highest first)
            results.sort(key=lambda item: item.confidence, reverse=True)
            
            # Limit results
            return results[:limit]
    
    async def get_version_history(self, item_id: str) -> List[KnowledgeItem]:
        """
        Get version history for a knowledge item
        
        Args:
            item_id: ID of the item
            
        Returns:
            List of versions in chronological order
        """
        async with self._lock:
            versions = []
            
            # Check if ID is in version history
            if item_id in self.version_history:
                # Add all versions
                for version_id in self.version_history[item_id]:
                    if version_id in self.items:
                        versions.append(self.items[version_id])
            
            # Check if ID is a current item
            if item_id in self.items:
                versions.append(self.items[item_id])
            
            # Sort by version
            versions.sort(key=lambda item: item.version)
            
            return versions
    
    def _save_to_disk(self) -> None:
        """Save knowledge repository to disk"""
        if not self.storage_dir:
            return
        
        try:
            # Save items
            items_path = os.path.join(self.storage_dir, "knowledge_items.json")
            with open(items_path, "w") as f:
                items_dict = {
                    item_id: item.to_dict()
                    for item_id, item in self.items.items()
                }
                json.dump(items_dict, f, indent=2)
            
            # Save version history
            history_path = os.path.join(self.storage_dir, "version_history.json")
            with open(history_path, "w") as f:
                json.dump(self.version_history, f, indent=2)
            
            logger.info(f"Saved {len(self.items)} knowledge items to disk")
        except Exception as e:
            logger.error(f"Error saving knowledge repository to disk: {e}")
    
    def _load_from_disk(self) -> None:
        """Load knowledge repository from disk"""
        if not self.storage_dir:
            return
        
        try:
            # Load items
            items_path = os.path.join(self.storage_dir, "knowledge_items.json")
            if os.path.exists(items_path):
                with open(items_path, "r") as f:
                    items_dict = json.load(f)
                    for item_id, item_data in items_dict.items():
                        self.items[item_id] = KnowledgeItem.from_dict(item_data)
            
            # Load version history
            history_path = os.path.join(self.storage_dir, "version_history.json")
            if os.path.exists(history_path):
                with open(history_path, "r") as f:
                    self.version_history = json.load(f)
            
            logger.info(f"Loaded {len(self.items)} knowledge items from disk")
        except Exception as e:
            logger.error(f"Error loading knowledge repository from disk: {e}")

# Singleton instance
_default_repository = None

def get_default_repository() -> KnowledgeRepository:
    """Get the default knowledge repository instance"""
    global _default_repository
    if _default_repository is None:
        storage_dir = os.environ.get("KNOWLEDGE_REPOSITORY_DIR")
        _default_repository = KnowledgeRepository(storage_dir)
    return _default_repository

# Helper functions
async def store_fact(title: str, content: Any, confidence: float = 1.0, tags: List[str] = None) -> str:
    """
    Store a fact in the knowledge repository
    
    Args:
        title: Fact title
        content: Fact content
        confidence: Confidence level (0.0-1.0)
        tags: Tags for the fact
        
    Returns:
        ID of the stored fact
    """
    repo = get_default_repository()
    item = KnowledgeItem(
        knowledge_type=KnowledgeType.FACT,
        title=title,
        content=content,
        confidence=confidence,
        tags=tags or [],
        created_by="system"
    )
    return await repo.add_item(item)

async def store_user_preference(title: str, content: Any, tags: List[str] = None) -> str:
    """
    Store a user preference in the knowledge repository
    
    Args:
        title: Preference title
        content: Preference content
        tags: Tags for the preference
        
    Returns:
        ID of the stored preference
    """
    repo = get_default_repository()
    item = KnowledgeItem(
        knowledge_type=KnowledgeType.PREFERENCE,
        title=title,
        content=content,
        confidence=1.0,  # Preferences are always 100% confident
        tags=tags or [],
        created_by="user"
    )
    return await repo.add_item(item)

async def find_knowledge(query: str, knowledge_type: Optional[KnowledgeType] = None, limit: int = 5) -> List[KnowledgeItem]:
    """
    Find knowledge items by query
    
    Args:
        query: Search query
        knowledge_type: Filter by knowledge type
        limit: Maximum number of items to return
        
    Returns:
        List of matching knowledge items
    """
    repo = get_default_repository()
    return await repo.search(query=query, knowledge_type=knowledge_type, limit=limit)