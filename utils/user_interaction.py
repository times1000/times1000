"""
user_interaction.py - Manages interaction with users while minimizing interruptions
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("UserInteraction")

class QuestionPriority(Enum):
    """Priority levels for questions to the user"""
    CRITICAL = 0  # Must be answered immediately
    HIGH = 1      # Important question but can be delayed briefly
    MEDIUM = 2    # Standard question
    LOW = 3       # Can be delayed significantly

class QuestionCategory(Enum):
    """Categories of questions to help with batching similar questions"""
    CLARIFICATION = "clarification"
    PERMISSION = "permission"
    PREFERENCE = "preference"
    INFORMATION = "information"
    VERIFICATION = "verification"
    FEEDBACK = "feedback"
    OTHER = "other"

@dataclass(order=True)
class UserQuestion:
    """Represents a question to be asked to the user"""
    priority: QuestionPriority
    created_at: datetime = field(compare=False)
    question_id: str = field(compare=False)
    question_text: str = field(compare=False)
    category: QuestionCategory = field(compare=False)
    context: Dict[str, Any] = field(default_factory=dict, compare=False)
    is_answered: bool = field(default=False, compare=False)
    answer: Optional[str] = field(default=None, compare=False)
    timeout_seconds: Optional[float] = field(default=None, compare=False)
    callback: Optional[Callable[[str], Awaitable[None]]] = field(default=None, compare=False)
    
    def format_with_context(self) -> str:
        """Format the question with its context for presentation to the user"""
        formatted = f"{self.question_text}"
        
        # Add context if it exists and has useful information
        if self.context:
            # Filter out internal keys starting with underscore
            context_items = {k: v for k, v in self.context.items() if not k.startswith('_')}
            if context_items:
                formatted += "\n\nContext:"
                for key, value in context_items.items():
                    value_str = str(value)
                    # Truncate long values
                    if len(value_str) > 100:
                        value_str = value_str[:97] + "..."
                    formatted += f"\n- {key}: {value_str}"
        
        return formatted

class UserInteractionController:
    """
    Controls interactions with the user to minimize interruptions.
    
    Strategies:
    1. Question batching: Collect questions and present them together
    2. Priority-based filtering: Only ask critical questions immediately
    3. Context preservation: Attach context to questions for better understanding
    4. Preference learning: Remember user preferences to avoid asking again
    """
    
    def __init__(self, 
                max_batch_size: int = 3, 
                batch_timeout_seconds: float = 30.0,
                min_priority_for_immediate: QuestionPriority = QuestionPriority.HIGH):
        """
        Initialize the user interaction controller.
        
        Args:
            max_batch_size: Maximum number of questions to batch together
            batch_timeout_seconds: Maximum time to wait before asking batched questions
            min_priority_for_immediate: Minimum priority for immediate questions
        """
        self.question_queue: List[UserQuestion] = []
        self.max_batch_size = max_batch_size
        self.batch_timeout_seconds = batch_timeout_seconds
        self.min_priority_for_immediate = min_priority_for_immediate
        self.user_preferences: Dict[str, Any] = {}
        self.last_batch_time = datetime.now()
        self._lock = asyncio.Lock()
        self._processing_task: Optional[asyncio.Task] = None
        
    async def ask_question(self, 
                    question_text: str, 
                    category: QuestionCategory = QuestionCategory.OTHER,
                    priority: QuestionPriority = QuestionPriority.MEDIUM,
                    context: Dict[str, Any] = None,
                    timeout_seconds: Optional[float] = None,
                    callback: Optional[Callable[[str], Awaitable[None]]] = None) -> str:
        """
        Ask a question to the user, with possible batching based on priority.
        
        Args:
            question_text: The question to ask
            category: Question category for batching similar questions
            priority: Priority level of the question
            context: Additional context to provide with the question
            timeout_seconds: Optional timeout for waiting for an answer
            callback: Optional callback function to call with the answer
            
        Returns:
            The user's answer
        """
        # Check if we already have a preference that answers this question
        preference_key = self._generate_preference_key(question_text, category)
        if category == QuestionCategory.PREFERENCE and preference_key in self.user_preferences:
            logger.info(f"Using stored preference for: {question_text}")
            return self.user_preferences[preference_key]
        
        # Create a new question
        question = UserQuestion(
            priority=priority,
            created_at=datetime.now(),
            question_id=f"q_{len(self.question_queue) + 1}",
            question_text=question_text,
            category=category,
            context=context or {},
            timeout_seconds=timeout_seconds,
            callback=callback
        )
        
        # If critical or high priority, ask immediately
        if priority.value <= self.min_priority_for_immediate.value:
            return await self._ask_single_question(question)
        
        # Otherwise, add to queue for batching
        async with self._lock:
            self.question_queue.append(question)
            
            # Start processing task if not already running
            if self._processing_task is None or self._processing_task.done():
                self._processing_task = asyncio.create_task(self._process_question_queue())
        
        # Wait for the question to be answered
        while not question.is_answered:
            await asyncio.sleep(0.1)
            
        return question.answer or ""
    
    async def _ask_single_question(self, question: UserQuestion) -> str:
        """Ask a single question directly to the user"""
        formatted_question = question.format_with_context()
        
        print(f"\n[QUESTION] {formatted_question}")
        try:
            # Handle timeout if specified
            if question.timeout_seconds:
                answer = await asyncio.wait_for(
                    self._get_user_input(),
                    timeout=question.timeout_seconds
                )
            else:
                answer = await self._get_user_input()
                
            # Store preference if it's a preference question
            if question.category == QuestionCategory.PREFERENCE:
                preference_key = self._generate_preference_key(question.question_text, question.category)
                self.user_preferences[preference_key] = answer
            
            # Call callback if provided
            if question.callback:
                await question.callback(answer)
            
            # Mark as answered
            question.is_answered = True
            question.answer = answer
            
            return answer
            
        except asyncio.TimeoutError:
            print(f"\n[TIMEOUT] Question timed out after {question.timeout_seconds} seconds. Proceeding with default behavior.")
            question.is_answered = True
            question.answer = ""
            return ""
    
    async def _ask_batched_questions(self, questions: List[UserQuestion]) -> Dict[str, str]:
        """Ask multiple questions in a batch"""
        if not questions:
            return {}
            
        print("\n[QUESTIONS] Please answer the following questions:")
        
        for i, question in enumerate(questions, 1):
            formatted_question = question.format_with_context()
            print(f"\n{i}. {formatted_question}")
        
        answers = {}
        for i, question in enumerate(questions, 1):
            print(f"\nAnswer for question {i}:")
            answer = await self._get_user_input()
            answers[question.question_id] = answer
            
            # Store preference if it's a preference question
            if question.category == QuestionCategory.PREFERENCE:
                preference_key = self._generate_preference_key(question.question_text, question.category)
                self.user_preferences[preference_key] = answer
            
            # Call callback if provided
            if question.callback:
                await question.callback(answer)
            
            # Mark as answered
            question.is_answered = True
            question.answer = answer
        
        return answers
    
    async def _process_question_queue(self):
        """Process the question queue, batching questions when appropriate"""
        while True:
            async with self._lock:
                # Check if we have questions to process
                if not self.question_queue:
                    return
                
                current_time = datetime.now()
                time_since_last_batch = (current_time - self.last_batch_time).total_seconds()
                
                # Process if we have enough questions or enough time has passed
                should_process = (
                    len(self.question_queue) >= self.max_batch_size or
                    time_since_last_batch >= self.batch_timeout_seconds
                )
                
                if not should_process:
                    # Release lock and wait
                    self.question_queue.sort()  # Sort by priority
                    
            if not should_process:
                await asyncio.sleep(0.5)
                continue
                
            # We should process the queue
            async with self._lock:
                # Take up to max_batch_size questions, prioritized
                self.question_queue.sort()  # Sort by priority
                batch = self.question_queue[:self.max_batch_size]
                
                # Group by category if possible
                by_category = {}
                for q in batch:
                    if q.category not in by_category:
                        by_category[q.category] = []
                    by_category[q.category].append(q)
                
                # Remove from queue
                self.question_queue = self.question_queue[self.max_batch_size:]
                self.last_batch_time = current_time
            
            # Process batch by category
            for category, questions in by_category.items():
                await self._ask_batched_questions(questions)
    
    async def _get_user_input(self) -> str:
        """Get input from the user (can be mocked for testing)"""
        # This is a simple wrapper that could be enhanced with readline support, etc.
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, input, "> ")
    
    def _generate_preference_key(self, question: str, category: QuestionCategory) -> str:
        """Generate a preference key from a question"""
        # Create a simplified key based on the question
        # This is a simple implementation - could be enhanced with NLP in the future
        simplified = question.lower()
        
        # Remove common question words and punctuation
        for word in ["what", "which", "how", "do", "you", "prefer", "want", "like", 
                    "would", "should", "could", "?", ".", ","]:
            simplified = simplified.replace(word, " ")
            
        # Normalize whitespace
        simplified = " ".join(simplified.split())
        
        return f"{category.value}:{simplified}"