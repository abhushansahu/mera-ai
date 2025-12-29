from typing import Optional

from app.adapters.chroma import ChromaMemoryAdapter
from app.infrastructure.config.settings import get_settings
from app.spaces.space_model import SpaceConfig

MemoryManager = ChromaMemoryAdapter


def get_memory_manager(collection_name: Optional[str] = None) -> MemoryManager:
    """Get memory manager with optional collection name override.
    
    Args:
        collection_name: Optional collection name. If None, uses default from settings.
    
    Returns:
        ChromaMemoryAdapter instance
    """
    settings = get_settings()
    return ChromaMemoryAdapter(
        host=settings.chroma_host,
        port=settings.chroma_port,
        collection_name=collection_name or settings.chroma_collection_name,
        persist_directory=settings.chroma_persist_dir,
    )


def get_memory_manager_for_space(space_config: SpaceConfig) -> MemoryManager:
    """Get memory manager for a specific space.
    
    Args:
        space_config: Space configuration
    
    Returns:
        ChromaMemoryAdapter instance with space-specific collection
    """
    settings = get_settings()
    return ChromaMemoryAdapter(
        host=settings.chroma_host,
        port=settings.chroma_port,
        collection_name=space_config.mem0_collection_name,
        persist_directory=settings.chroma_persist_dir,
    )
