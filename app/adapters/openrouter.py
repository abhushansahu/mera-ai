"""OpenRouter LLM adapter."""

import asyncio
import time
from typing import List, Optional

import httpx

from app.core import LLMMessage, LLMResponse
from app.config import get_settings


def _build_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://localhost", "X-Title": "Unified AI Assistant"}

_async_client: Optional[httpx.AsyncClient] = None
_last_request_time: dict[str, float] = {}
_min_request_interval: float = 0.1

async def _get_async_client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None:
        _async_client = httpx.AsyncClient(timeout=60.0, limits=httpx.Limits(max_keepalive_connections=20, max_connections=100))
    return _async_client

async def _close_async_client() -> None:
    global _async_client
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None


class OpenRouterLLMAdapter:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = (base_url or settings.openrouter_base_url).rstrip("/")
        self.url = f"{self.base_url}/chat/completions"

    async def chat(self, messages: List[LLMMessage], model: str, max_retries: int = 3, retry_delay: float = 1.0, **kwargs) -> LLMResponse:
        client = await _get_async_client()
        global _last_request_time
        last_time = _last_request_time.get(model, 0)
        elapsed = time.time() - last_time
        if elapsed < _min_request_interval:
            await asyncio.sleep(_min_request_interval - elapsed)
        _last_request_time[model] = time.time()
        
        payload = {"model": model, "messages": [{"role": msg.role, "content": msg.content} for msg in messages], **kwargs}
        last_exception = None
        for attempt in range(max_retries):
            try:
                response = await client.post(self.url, headers=_build_headers(self.api_key), json=payload)
                response.raise_for_status()
                data = response.json()
                return LLMResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=model,
                    metadata={"attempt": attempt + 1, "usage": data.get("usage", {})},
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    raise
                last_exception = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
            except Exception:
                raise
        
        if last_exception:
            raise last_exception
        raise RuntimeError("Failed to get response after retries")


__all__ = ["OpenRouterLLMAdapter", "_close_async_client", "_get_async_client"]
