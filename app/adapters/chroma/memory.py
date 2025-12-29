import asyncio
import os
from typing import List, Optional
from uuid import uuid4

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.memory import Memory
from app.core.types import UserID
from app.infrastructure.cache import get_cached, set_cached
from app.infrastructure.embeddings import get_embeddings


class ChromaMemoryAdapter:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        collection_name: Optional[str] = None,
        persist_directory: Optional[str] = None,
    ) -> None:
        self.host = host or os.getenv("CHROMA_HOST")
        self.port = port or int(os.getenv("CHROMA_PORT", "8000"))
        self.collection_name = collection_name or os.getenv("CHROMA_COLLECTION_NAME", "memories")
        self.persist_directory = persist_directory or os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        
        if self.host:
            self._client = chromadb.HttpClient(host=self.host, port=self.port)
        else:
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    async def store(
        self,
        user_id: UserID,
        text: str,
        metadata: Optional[dict] = None,
    ) -> None:
        embeddings = await get_embeddings([text])
        embedding = embeddings[0]
        
        chroma_metadata = {
            "user_id": user_id,
            **(metadata or {}),
        }
        
        memory_id = str(uuid4())
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
        user_id: UserID,
        query: str,
        limit: int = 5,
    ) -> List[Memory]:
        cache_key = (user_id, query, limit)
        cached_result = await get_cached("chroma_search", cache_key, None)
        if cached_result is not None:
            if isinstance(cached_result, list):
                return [Memory(**item) if isinstance(item, dict) else item for item in cached_result]
            return cached_result
        
        query_embeddings = await get_embeddings([query])
        query_embedding = query_embeddings[0]
        
        collection = self._get_collection()
        results = await asyncio.to_thread(
            collection.query,
            query_embeddings=[query_embedding],
            n_results=limit,
            where={"user_id": user_id},
        )
        
        memories: List[Memory] = []
        if results["ids"] and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                memory = Memory(
                    text=results["documents"][0][i] if results["documents"] else "",
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    score=1.0 - results["distances"][0][i] if results["distances"] else 0.0,
                )
                memories.append(memory)
        
        cache_data = [{"text": m.text, "metadata": m.metadata, "score": m.score} for m in memories]
        await set_cached("chroma_search", cache_key, cache_data, None, ttl=1800)
        
        return memories
