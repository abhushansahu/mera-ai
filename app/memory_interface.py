"""Memory manager protocol/interface for abstraction."""

from typing import Any, Dict, List, Optional, Protocol


class MemoryManager(Protocol):
    """Protocol defining the memory manager interface.
    
    Both Mem0Wrapper and ChromaMemoryManager implement this interface,
    allowing for easy swapping and A/B testing.
    """

    async def store(
        self,
        user_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store memory asynchronously.
        
        Args:
            user_id: User identifier for memory isolation
            text: Text content to store
            metadata: Optional metadata dictionary
        """
        ...

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search memories asynchronously.
        
        Args:
            user_id: User identifier for memory isolation
            query: Search query text
            limit: Maximum number of results to return
        
        Returns:
            List of memory dictionaries with 'text', 'metadata', and optionally 'score' keys
        """
        ...
