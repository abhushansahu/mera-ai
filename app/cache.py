"""Async caching layer for performance optimization."""

import hashlib
import json
from typing import Any, Dict, Optional

from aiocache import Cache
from aiocache.serializers import JsonSerializer


# Global cache instance
_cache: Optional[Cache] = None


async def get_cache() -> Cache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        _cache = Cache(
            Cache.MEMORY,
            serializer=JsonSerializer(),
            namespace="mera_ai",
            timeout=None,  # No global timeout, use TTL per key
        )
    return _cache


def _make_key(prefix: str, *args: Any, **kwargs: Any) -> str:
    """Create a cache key from prefix and arguments."""
    key_data = {
        "prefix": prefix,
        "args": args,
        "kwargs": sorted(kwargs.items()) if kwargs else {},
    }
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.sha256(key_str.encode()).hexdigest()


async def get_cached(
    prefix: str,
    key_args: tuple,
    key_kwargs: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    """Get a value from cache."""
    cache = await get_cache()
    cache_key = _make_key(prefix, *key_args, **(key_kwargs or {}))
    try:
        return await cache.get(cache_key)
    except Exception:
        return None


async def set_cached(
    prefix: str,
    key_args: tuple,
    value: Any,
    key_kwargs: Optional[Dict[str, Any]] = None,
    ttl: int = 3600,
) -> None:
    """Set a value in cache."""
    cache = await get_cache()
    cache_key = _make_key(prefix, *key_args, **(key_kwargs or {}))
    try:
        await cache.set(cache_key, value, ttl=ttl)
    except Exception:
        pass
