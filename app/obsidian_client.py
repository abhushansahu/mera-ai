from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from app.cache import get_cached, set_cached
from app.config import settings


@dataclass
class ObsidianClient:
    """Real Obsidian integration via Local REST API plugin with async support.

    Requires Obsidian with the "Local REST API" plugin installed and enabled.
    Default URL: http://localhost:27124
    Set OBSIDIAN_REST_URL and OBSIDIAN_REST_TOKEN environment variables.
    """

    base_url: str
    token: Optional[str]
    _client: Optional[httpx.AsyncClient] = None

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None) -> None:
        self.base_url = base_url or settings.obsidian_rest_url or "http://localhost:27124"
        self.token = token or settings.obsidian_rest_token
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client with connection pooling."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=5.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
            )
        return self._client

    async def close(self) -> None:
        """Close the async HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def create_note(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Create a new note in Obsidian vault via REST API asynchronously."""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        # Sanitize title for filename
        filename = title.replace("/", "-").replace("\\", "-").strip()
        if not filename.endswith(".md"):
            filename += ".md"

        # Add tags to content if provided
        if tags:
            tag_line = " ".join([f"#{tag}" for tag in tags])
            content = f"{tag_line}\n\n{content}"

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/vault/create",
                headers=headers,
                json={"path": filename, "content": content},
            )
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            # Log but don't fail the entire request if Obsidian is unavailable
            # In production, you might want to use a logger here
            print(f"Obsidian API error (create_note): {e}")

    async def search(
        self,
        query: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search Obsidian vault via REST API asynchronously with caching."""
        cache_key = ("obsidian_search", query, limit)
        cached_result = await get_cached("obsidian_search", cache_key)
        if cached_result is not None:
            return cached_result
        
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/vault/search",
                headers=headers,
                json={"query": query, "limit": limit},
            )
            response.raise_for_status()
            results = response.json()
            if isinstance(results, list):
                final_results = results
            elif isinstance(results, dict) and "results" in results:
                final_results = results["results"]
            else:
                final_results = []
            
            await set_cached("obsidian_search", cache_key, final_results, ttl=1800)
            return final_results
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(f"Obsidian API error (search): {e}")
            return []


