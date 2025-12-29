"""Obsidian integration via Local REST API plugin."""

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
from aiocache import Cache
from aiocache.serializers import JsonSerializer

from app.config import get_settings

logger = logging.getLogger(__name__)

# Cache setup (inlined)
_cache: Optional[Cache] = None

async def _get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache(Cache.MEMORY, serializer=JsonSerializer(), namespace="mera_ai", timeout=None)
    return _cache

def _make_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    key_data = {"prefix": prefix, "args": args, "kwargs": sorted(kwargs.items()) if kwargs else {}}
    return hashlib.sha256(json.dumps(key_data, sort_keys=True, default=str).encode()).hexdigest()

async def _get_cached(prefix: str, key_args: tuple) -> Optional[Any]:
    try:
        cache = await _get_cache()
        return await cache.get(_make_key(prefix, *key_args))
    except Exception:
        return None

async def _set_cached(prefix: str, key_args: tuple, value: Any, ttl: int = 1800) -> None:
    try:
        cache = await _get_cache()
        await cache.set(_make_key(prefix, *key_args), value, ttl=ttl)
    except Exception:
        pass


@dataclass
class ObsidianAdapter:
    """Obsidian integration via Local REST API plugin with async support."""
    base_url: str
    token: Optional[str] = None
    vault_path: Optional[str] = None
    _client: Optional[httpx.AsyncClient] = None

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None, vault_path: Optional[str] = None) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.obsidian_rest_url or "http://localhost:27124"
        self.token = token or settings.obsidian_rest_token
        self.vault_path = vault_path or settings.obsidian_vault_path
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=5.0, limits=httpx.Limits(max_keepalive_connections=10, max_connections=50))
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def create_note(self, title: str, content: str, tags: Optional[List[str]] = None) -> None:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        filename = title.replace("/", "-").replace("\\", "-").strip()
        if not filename.endswith(".md"):
            filename += ".md"
        if tags:
            content = " ".join([f"#{tag}" for tag in tags]) + "\n\n" + content
        try:
            client = await self._get_client()
            payload = {"path": filename, "content": content}
            if self.vault_path:
                payload["vault"] = self.vault_path
            response = await client.post(f"{self.base_url}/vault/create", headers=headers, json=payload)
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.warning(f"Obsidian API error (create_note): {e}")

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        cache_key = (query, limit)
        cached_result = await _get_cached("obsidian_search", cache_key)
        if cached_result is not None:
            return cached_result
        
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            client = await self._get_client()
            payload = {"query": query, "limit": limit}
            if self.vault_path:
                payload["vault"] = self.vault_path
            response = await client.post(f"{self.base_url}/vault/search", headers=headers, json=payload)
            response.raise_for_status()
            results = response.json()
            final_results = results if isinstance(results, list) else (results.get("results", []) if isinstance(results, dict) else [])
            await _set_cached("obsidian_search", cache_key, final_results, ttl=1800)
            return final_results
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.warning(f"Obsidian API error (search): {e}")
            return []


# Backward compatibility
ObsidianClient = ObsidianAdapter
