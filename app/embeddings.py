"""Embedding generation using OpenRouter for consistency with Mem0."""

import asyncio
from typing import List, Optional

import httpx

from app.config import settings
from app.llm_client import build_headers, get_async_client


async def get_embeddings(
    texts: List[str],
    model: str = "text-embedding-3-small",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> List[List[float]]:
    """Generate embeddings using OpenRouter's embedding endpoint.
    
    Uses the same embedding model as Mem0 (text-embedding-3-small) for consistency.
    
    Args:
        texts: List of text strings to embed
        model: Embedding model name (default: text-embedding-3-small)
        api_key: OpenRouter API key (defaults to settings)
        base_url: OpenRouter base URL (defaults to settings)
        client: Optional HTTP client (uses shared client if not provided)
    
    Returns:
        List of embedding vectors (each is a list of floats)
    """
    key = api_key or settings.openrouter_api_key
    url = (base_url or settings.openrouter_base_url).rstrip("/") + "/embeddings"
    
    if client is None:
        client = await get_async_client()
        use_shared = True
    else:
        use_shared = False
    
    try:
        # OpenRouter embeddings endpoint expects same format as OpenAI
        payload = {
            "model": model,
            "input": texts,
        }
        
        response = await client.post(url, headers=build_headers(key), json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Extract embeddings from response
        # OpenAI/OpenRouter format: {"data": [{"embedding": [...]}, ...]}
        embeddings = [item["embedding"] for item in data["data"]]
        return embeddings
    finally:
        if not use_shared and client is not None:
            await client.aclose()
