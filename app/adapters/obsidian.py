"""Obsidian integration via Local REST API plugin."""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
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

    def _normalize_note_path(self, note_path: str) -> str:
        cleaned = note_path.strip().replace("\\", "/")
        if cleaned.startswith("/"):
            cleaned = cleaned[1:]
        if not cleaned.endswith(".md"):
            cleaned += ".md"
        return cleaned

    def _local_vault_root(self) -> Optional[Path]:
        # If the vault path is local, we can directly manage markdown files.
        if not self.vault_path:
            return None
        try:
            vault_root = Path(self.vault_path).expanduser().resolve()
            vault_root.mkdir(parents=True, exist_ok=True)
            return vault_root
        except Exception:
            return None

    async def upsert_note(self, note_path: str, content: str) -> None:
        normalized = self._normalize_note_path(note_path)
        local_root = self._local_vault_root()
        if local_root is not None:
            full_path = local_root / normalized
            await asyncio.to_thread(lambda: full_path.parent.mkdir(parents=True, exist_ok=True))
            await asyncio.to_thread(full_path.write_text, content, "utf-8")
            return

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            client = await self._get_client()
            payload = {"path": normalized, "content": content}
            if self.vault_path:
                payload["vault"] = self.vault_path
            response = await client.post(f"{self.base_url}/vault/create", headers=headers, json=payload)
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.warning(f"Obsidian API error (upsert_note): {e}")

    async def append_note(self, note_path: str, content: str) -> None:
        normalized = self._normalize_note_path(note_path)
        local_root = self._local_vault_root()
        if local_root is not None:
            full_path = local_root / normalized
            await asyncio.to_thread(lambda: full_path.parent.mkdir(parents=True, exist_ok=True))
            existing = ""
            if full_path.exists():
                existing = await asyncio.to_thread(full_path.read_text, "utf-8")
            joined = f"{existing}\n{content}".strip() + "\n"
            await asyncio.to_thread(full_path.write_text, joined, "utf-8")
            return

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            client = await self._get_client()
            payload = {"path": normalized, "content": content}
            if self.vault_path:
                payload["vault"] = self.vault_path
            response = await client.post(f"{self.base_url}/vault/append", headers=headers, json=payload)
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.warning(f"Obsidian API error (append_note): {e}")

    async def read_note(self, note_path: str) -> str:
        normalized = self._normalize_note_path(note_path)
        local_root = self._local_vault_root()
        if local_root is not None:
            full_path = local_root / normalized
            if not full_path.exists():
                return ""
            try:
                return await asyncio.to_thread(full_path.read_text, "utf-8")
            except Exception as e:
                logger.warning(f"Failed reading local note {normalized}: {e}")
                return ""
        return ""

    async def list_notes(self, prefix: str = "") -> List[str]:
        local_root = self._local_vault_root()
        if local_root is None:
            return []
        clean_prefix = prefix.strip().replace("\\", "/").strip("/")
        target = local_root / clean_prefix if clean_prefix else local_root
        if not target.exists():
            return []
        files = await asyncio.to_thread(lambda: sorted(target.rglob("*.md")))
        return [str(f.relative_to(local_root)).replace("\\", "/") for f in files]

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
