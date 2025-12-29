"""LangChain retriever implementations for Chroma and Obsidian."""

from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from app.memory_factory import MemoryManager, get_memory_manager
from app.obsidian_client import ObsidianClient


class ChromaRetriever(BaseRetriever):
    """LangChain retriever for Chroma memory store."""

    memory: MemoryManager
    user_id: str
    k: int = 5

    def __init__(self, memory: Optional[MemoryManager] = None, user_id: str = "default", k: int = 5, **kwargs):
        """Initialize ChromaRetriever.
        
        Args:
            memory: MemoryManager instance (defaults to factory)
            user_id: User identifier for memory isolation
            k: Number of documents to retrieve
        """
        super().__init__(**kwargs)
        self.memory = memory or get_memory_manager()
        self.user_id = user_id
        self.k = k

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """Synchronous retrieval (not recommended for async memory managers)."""
        import asyncio
        return asyncio.run(self._aget_relevant_documents(query))

    async def _aget_relevant_documents(self, query: str) -> List[Document]:
        """Asynchronous retrieval."""
        results = await self.memory.search(
            user_id=self.user_id,
            query=query,
            limit=self.k,
        )
        
        documents = []
        for result in results:
            doc = Document(
                page_content=result.get("text", ""),
                metadata=result.get("metadata", {}),
            )
            documents.append(doc)
        
        return documents


class ObsidianRetriever(BaseRetriever):
    """LangChain retriever for Obsidian vault."""

    obsidian: ObsidianClient
    k: int = 5

    def __init__(self, obsidian: Optional[ObsidianClient] = None, k: int = 5, **kwargs):
        """Initialize ObsidianRetriever.
        
        Args:
            obsidian: ObsidianClient instance (defaults to new instance)
            k: Number of documents to retrieve
        """
        super().__init__(**kwargs)
        self.obsidian = obsidian or ObsidianClient()
        self.k = k

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """Synchronous retrieval (not recommended for async Obsidian client)."""
        import asyncio
        return asyncio.run(self._aget_relevant_documents(query))

    async def _aget_relevant_documents(self, query: str) -> List[Document]:
        """Asynchronous retrieval."""
        results = await self.obsidian.search(query=query, limit=self.k)
        
        documents = []
        for result in results:
            content = result.get("content", "")
            title = result.get("path", "") or result.get("title", "")
            
            doc = Document(
                page_content=content,
                metadata={
                    "source": "obsidian",
                    "path": title,
                    **{k: v for k, v in result.items() if k not in ("content", "path", "title")},
                },
            )
            documents.append(doc)
        
        return documents
