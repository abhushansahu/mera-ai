from app.adapters.chroma import ChromaMemoryAdapter
from app.infrastructure.config.settings import get_settings

MemoryManager = ChromaMemoryAdapter


def get_memory_manager() -> MemoryManager:
    settings = get_settings()
    return ChromaMemoryAdapter(
        host=settings.chroma_host,
        port=settings.chroma_port,
        collection_name=settings.chroma_collection_name,
        persist_directory=settings.chroma_persist_dir,
    )
