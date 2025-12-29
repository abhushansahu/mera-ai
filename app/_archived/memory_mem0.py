import asyncio
import os
from typing import Any, Dict, List, Optional

from mem0 import MemoryClient

from app.cache import get_cached, set_cached
from app.config import settings


class Mem0Wrapper:
    """Thin functional-style wrapper around Mem0 client with async support.

    This wrapper is intentionally small so it can be replaced or mocked easily
    in unit tests.

    Supports both self-hosted (via MEM0_HOST) and external (via MEM0_API_KEY) Mem0 instances.
    Mem0 operations are wrapped in async functions using asyncio.to_thread for non-blocking execution.
    """

    def __init__(
        self,
        client: Optional[MemoryClient] = None,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            # Prefer provided parameters, then settings, then environment variables
            mem0_api_key = api_key or settings.mem0_api_key or os.getenv("MEM0_API_KEY")
            mem0_host = host or settings.mem0_host or os.getenv("MEM0_HOST")

            # If using self-hosted instance, host is required
            if mem0_host:
                # For self-hosted, API key is optional (use placeholder if not provided)
                # The self-hosted Mem0 server doesn't actually validate this key
                if not mem0_api_key:
                    mem0_api_key = "self-hosted-mem0-no-key-required"
                self._client = MemoryClient(api_key=mem0_api_key, host=mem0_host)
            elif mem0_api_key:
                # External Mem0 instance
                self._client = MemoryClient(api_key=mem0_api_key)
            else:
                raise ValueError(
                    "Either MEM0_HOST (for self-hosted) or MEM0_API_KEY (for external) is required. "
                    "Please set one in your environment variables or .env file."
                )

    async def store(
        self,
        user_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store memory asynchronously."""
        # Mem0 client.add expects messages parameter (can be string or list)
        payload: Dict[str, Any] = {"user_id": user_id, "messages": text}
        if metadata:
            payload["metadata"] = metadata
        # Fire-and-forget semantics; errors can be surfaced later if needed.
        # Run in thread pool to avoid blocking
        await asyncio.to_thread(self._client.add, **payload)

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search memories asynchronously with caching."""
        cache_key = ("mem0_search", user_id, query, limit)
        cached_result = await get_cached("mem0_search", cache_key)
        if cached_result is not None:
            return cached_result
        
        result = await asyncio.to_thread(
            self._client.search,
            user_id=user_id,
            query=query,
            limit=limit,
        )
        
        await set_cached("mem0_search", cache_key, result, ttl=1800)
        return result


