"""Provider-aware LLM adapter (OpenRouter + local OpenAI-compatible backends)."""

import asyncio
import time
from typing import List, Optional

import httpx

from app.core import LLMMessage, LLMResponse
from app.config import get_settings


def build_headers(api_key: Optional[str], include_openrouter_meta: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if include_openrouter_meta:
        headers["HTTP-Referer"] = "https://localhost"
        headers["X-Title"] = "Unified AI Assistant"
    return headers


def _chat_completion_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _provider_default_base_url(provider: str) -> str:
    settings = get_settings()
    if provider == "lmstudio":
        return settings.lmstudio_base_url
    if provider == "cursor-local":
        return settings.cursor_agent_base_url
    return settings.openrouter_base_url


def _provider_default_api_key(provider: str) -> Optional[str]:
    settings = get_settings()
    if provider == "lmstudio":
        return settings.lmstudio_api_key
    if provider == "cursor-local":
        return settings.cursor_agent_api_key
    return settings.openrouter_api_key

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
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: str = "openrouter",
    ) -> None:
        self.provider = (provider or "openrouter").strip().lower()
        if self.provider not in {"openrouter", "lmstudio", "cursor-local"}:
            raise ValueError(f"Unsupported provider: {provider}")
        self.api_key = api_key if api_key is not None else _provider_default_api_key(self.provider)
        self.base_url = (base_url or _provider_default_base_url(self.provider)).rstrip("/")
        self.url = _chat_completion_url(self.base_url)
        if self.provider == "openrouter" and not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is required when provider is openrouter.")

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
            started = time.perf_counter()
            try:
                response = await client.post(
                    self.url,
                    headers=build_headers(self.api_key, include_openrouter_meta=self.provider == "openrouter"),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                latency_ms = (time.perf_counter() - started) * 1000
                return LLMResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=model,
                    metadata={
                        "provider": self.provider,
                        "base_url": self.base_url,
                        "attempt": attempt + 1,
                        "usage": data.get("usage", {}),
                        "latency_ms": round(latency_ms, 2),
                    },
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


__all__ = ["OpenRouterLLMAdapter", "_close_async_client", "_get_async_client", "build_headers"]
