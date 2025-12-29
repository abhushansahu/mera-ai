"""Chroma-based memory manager with same interface as Mem0Wrapper."""

import asyncio
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.cache import get_cached, set_cached
from app.config import settings
from app.embeddings import get_embeddings


class ChromaMemoryManager:
    """Chroma-based memory manager with same interface as Mem0Wrapper.
    
    Supports both embedded mode (default) and client-server mode.
    Uses OpenRouter embeddings for consistency with Mem0.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        collection_name: Optional[str] = None,
        persist_directory: Optional[str] = None,
    ) -> None:
        """Initialize ChromaMemoryManager.
        
        Args:
            host: Chroma server host (if using client-server mode)
            port: Chroma server port (if using client-server mode)
            collection_name: Name of the collection to use (default: "memories")
            persist_directory: Directory to persist data (for embedded mode)
        """
        self.host = host or os.getenv("CHROMA_HOST")
        self.port = port or int(os.getenv("CHROMA_PORT", "8000"))
        self.collection_name = collection_name or os.getenv("CHROMA_COLLECTION_NAME", "memories")
        self.persist_directory = persist_directory or os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        
        # Initialize Chroma client
        if self.host:
            # Client-server mode
            self._client = chromadb.HttpClient(
                host=self.host,
                port=self.port,
            )
        else:
            # Embedded mode (default)
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        
        # Get or create collection
        # Chroma collections are created lazily, so we just get a reference
        self._collection = None

    def _get_collection(self):
        """Get or create the collection."""
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},  # Use cosine similarity
            )
        return self._collection

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
        # Generate embedding for the text
        embeddings = await get_embeddings([text])
        embedding = embeddings[0]
        
        # Prepare metadata with user_id
        chroma_metadata = {
            "user_id": user_id,
            **(metadata or {}),
        }
        
        # Generate unique ID for this memory
        memory_id = str(uuid4())
        
        # Store in Chroma (run in thread pool to avoid blocking)
        collection = self._get_collection()
        await asyncio.to_thread(
            collection.add,
            ids=[memory_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[chroma_metadata],
        )

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search memories asynchronously with caching.
        
        Args:
            user_id: User identifier for memory isolation
            query: Search query text
            limit: Maximum number of results to return
        
        Returns:
            List of memory dictionaries with 'text', 'metadata', and 'score' keys
        """
        # Check cache
        cache_key = ("chroma_search", user_id, query, limit)
        cached_result = await get_cached("chroma_search", cache_key)
        if cached_result is not None:
            return cached_result
        
        # Generate embedding for query
        query_embeddings = await get_embeddings([query])
        query_embedding = query_embeddings[0]
        
        # Search in Chroma (run in thread pool to avoid blocking)
        collection = self._get_collection()
        results = await asyncio.to_thread(
            collection.query,
            query_embeddings=[query_embedding],
            n_results=limit,
            where={"user_id": user_id},  # Filter by user_id for isolation
        )
        
        # Format results to match Mem0 format
        formatted_results = []
        if results["ids"] and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                formatted_results.append({
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": 1.0 - results["distances"][0][i] if results["distances"] else 0.0,  # Convert distance to similarity
                })
        
        # Cache results
        await set_cached("chroma_search", cache_key, formatted_results, ttl=1800)
        return formatted_results
