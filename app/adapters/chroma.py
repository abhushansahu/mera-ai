"""ChromaDB memory adapter with inlined embeddings and caching."""

import asyncio
import hashlib
import json
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

import chromadb
import httpx
from chromadb.config import Settings as ChromaSettings
from aiocache import Cache
from aiocache.serializers import JsonSerializer

from app.core import Memory, UserID
from app.config import get_settings

# Cache setup
_cache: Optional[Cache] = None

async def _get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache(Cache.MEMORY, serializer=JsonSerializer(), namespace="mera_ai", timeout=None)
    return _cache

def _make_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    key_data = {"prefix": prefix, "args": args, "kwargs": sorted(kwargs.items()) if kwargs else {}}
    return hashlib.sha256(json.dumps(key_data, sort_keys=True, default=str).encode()).hexdigest()

async def _get_cached(prefix: str, key_args: tuple, key_kwargs: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    try:
        cache = await _get_cache()
        return await cache.get(_make_key(prefix, *key_args, **(key_kwargs or {})))
    except Exception:
        return None

async def _set_cached(prefix: str, key_args: tuple, value: Any, key_kwargs: Optional[Dict[str, Any]] = None, ttl: int = 3600) -> None:
    try:
        cache = await _get_cache()
        await cache.set(_make_key(prefix, *key_args, **(key_kwargs or {})), value, ttl=ttl)
    except Exception:
        pass

# Embeddings (inlined from infrastructure/embeddings.py)
async def _get_embeddings(texts: List[str], model: str = "text-embedding-3-small") -> List[List[float]]:
    import httpx
    settings = get_settings()
    async with httpx.AsyncClient(timeout=60.0) as client:
        url = settings.openrouter_base_url.rstrip("/") + "/embeddings"
        headers = {"Authorization": f"Bearer {settings.openrouter_api_key}", "HTTP-Referer": "https://localhost", "X-Title": "Unified AI Assistant"}
        payload = {"model": model, "input": texts}
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return [item["embedding"] for item in response.json()["data"]]


class ChromaMemoryAdapter:
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, collection_name: Optional[str] = None, persist_directory: Optional[str] = None) -> None:
        self.host = host or os.getenv("CHROMA_HOST")
        self.port = port or int(os.getenv("CHROMA_PORT", "8000"))
        self.collection_name = collection_name or os.getenv("CHROMA_COLLECTION_NAME", "memories")
        self.persist_directory = persist_directory or os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        if self.host:
            self._client = chromadb.HttpClient(host=self.host, port=self.port)
        else:
            self._client = chromadb.PersistentClient(path=self.persist_directory, settings=ChromaSettings(anonymized_telemetry=False))
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(name=self.collection_name, metadata={"hnsw:space": "cosine"})
        return self._collection

    async def store(self, user_id: UserID, text: str, metadata: Optional[dict] = None) -> None:
        embeddings = await _get_embeddings([text])
        chroma_metadata = {"user_id": user_id, **(metadata or {})}
        memory_id = str(uuid4())
        collection = self._get_collection()
        await asyncio.to_thread(collection.add, ids=[memory_id], embeddings=[embeddings[0]], documents=[text], metadatas=[chroma_metadata])

    async def search(self, user_id: UserID, query: str, limit: int = 5) -> List[Memory]:
        cache_key = (user_id, query, limit)
        cached_result = await _get_cached("chroma_search", cache_key)
        if cached_result is not None:
            if isinstance(cached_result, list):
                return [Memory(**item) if isinstance(item, dict) else item for item in cached_result]
            return cached_result
        
        query_embeddings = await _get_embeddings([query])
        collection = self._get_collection()
        results = await asyncio.to_thread(collection.query, query_embeddings=[query_embeddings[0]], n_results=limit, where={"user_id": user_id})
        
        memories: List[Memory] = []
        if results["ids"] and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                memories.append(Memory(
                    text=results["documents"][0][i] if results["documents"] else "",
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    score=1.0 - results["distances"][0][i] if results["distances"] else 0.0,
                ))
        
        cache_data = [{"text": m.text, "metadata": m.metadata, "score": m.score} for m in memories]
        await _set_cached("chroma_search", cache_key, cache_data, ttl=1800)
        return memories
