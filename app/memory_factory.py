"""Factory for creating memory managers based on configuration."""

from typing import Union

from app.config import settings
from app.memory_chroma import ChromaMemoryManager
from app.memory_mem0 import Mem0Wrapper

# Type alias for memory managers
MemoryManager = Union[Mem0Wrapper, ChromaMemoryManager]


def get_memory_manager() -> MemoryManager:
    """Get the appropriate memory manager based on configuration.
    
    Returns:
        MemoryManager instance (either Mem0Wrapper or ChromaMemoryManager)
    """
    if settings.use_chroma:
        return ChromaMemoryManager(
            host=settings.chroma_host,
            port=settings.chroma_port,
            collection_name=settings.chroma_collection_name,
            persist_directory=settings.chroma_persist_dir,
        )
    else:
        return Mem0Wrapper()
