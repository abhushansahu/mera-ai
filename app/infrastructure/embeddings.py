from typing import List, Optional

import httpx

from app.adapters.openrouter.llm import _build_headers, _get_async_client
from app.infrastructure.config.settings import get_settings


async def get_embeddings(
    texts: List[str],
    model: str = "text-embedding-3-small",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> List[List[float]]:
    settings = get_settings()
    key = api_key or settings.openrouter_api_key
    url = (base_url or settings.openrouter_base_url).rstrip("/") + "/embeddings"
    
    if client is None:
        client = await _get_async_client()
        use_shared = True
    else:
        use_shared = False
    
    try:
        payload = {
            "model": model,
            "input": texts,
        }
        
        response = await client.post(url, headers=_build_headers(key), json=payload)
        response.raise_for_status()
        data = response.json()
        
        embeddings = [item["embedding"] for item in data["data"]]
        return embeddings
    finally:
        if not use_shared and client is not None:
            await client.aclose()
