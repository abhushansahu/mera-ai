import asyncio
import time
from typing import Any, Dict, List, Literal, Optional

import httpx

from app.config import settings

Role = Literal["system", "user", "assistant"]

_async_client: Optional[httpx.AsyncClient] = None
_last_request_time: Dict[str, float] = {}
_min_request_interval: float = 0.1


def build_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://localhost",
        "X-Title": "Unified AI Assistant",
    }


async def get_async_client() -> httpx.AsyncClient:
    """Get or create shared async HTTP client."""
    global _async_client
    if _async_client is None:
        _async_client = httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )
    return _async_client


async def close_async_client() -> None:
    """Close the shared async HTTP client."""
    global _async_client
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None


async def call_openrouter_chat(
    model: str,
    messages: List[Dict[str, Any]],
    api_key: str | None = None,
    base_url: str | None = None,
    client: Optional[httpx.AsyncClient] = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> str:
    """Call OpenRouter's chat completions endpoint with retry logic and rate limiting."""
    key = api_key or settings.openrouter_api_key
    url = (base_url or settings.openrouter_base_url).rstrip("/") + "/chat/completions"
    payload: Dict[str, Any] = {"model": model, "messages": messages}

    if client is None:
        client = await get_async_client()
        use_shared = True
    else:
        use_shared = False

    global _last_request_time
    last_time = _last_request_time.get(model, 0)
    elapsed = time.time() - last_time
    if elapsed < _min_request_interval:
        await asyncio.sleep(_min_request_interval - elapsed)
    _last_request_time[model] = time.time()

    last_exception = None
    try:
        for attempt in range(max_retries):
            try:
                response = await client.post(url, headers=build_headers(key), json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    raise
                last_exception = e
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
            except Exception as e:
                raise
        
        if last_exception:
            raise last_exception
        raise RuntimeError("Failed to get response after retries")
    finally:
        if not use_shared and client is not None:
            await client.aclose()


