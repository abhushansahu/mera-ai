from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

import httpx
from app.observability import observe_langsmith
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine


class ContextSourceType(str, Enum):
    FILE = "FILE"
    DIRECTORY = "DIRECTORY"
    URL = "URL"
    API = "API"
    DATABASE = "DATABASE"
    MEMORY = "MEMORY"


@dataclass
class ContextSource:
    type: ContextSourceType
    path: str
    extra: Optional[Dict[str, Any]] = None


@dataclass
class ContextSpecification:
    query: str
    sources: List[ContextSource]


@dataclass
class FileExplorerAgent:
    """Explore local files/directories.

    The actual file I/O is injected so that this class remains easy to test.
    """

    read_paths: Callable[[Iterable[str]], Awaitable[str]]

    @observe_langsmith(name="file_explorer_agent")
    async def run(self, sources: List[ContextSource], query: str) -> str:
        paths = [s.path for s in sources if s.type in {ContextSourceType.FILE, ContextSourceType.DIRECTORY}]
        if not paths:
            return ""
        content = await self.read_paths(paths)
        return f"# File/Directory Findings\n\n{content}"


@dataclass
class LinkCrawlerAgent:
    """Fetch and summarize HTTP/URL/API docs.

    Network access is injected for easy mocking.
    """

    fetch_urls: Callable[[Iterable[str]], Awaitable[str]]

    @observe_langsmith(name="link_crawler_agent")
    async def run(self, sources: List[ContextSource], query: str) -> str:
        urls = [s.path for s in sources if s.type in {ContextSourceType.URL, ContextSourceType.API}]
        if not urls:
            return ""
        docs = await self.fetch_urls(urls)
        return f"# Link/API Findings\n\n{docs}"


@dataclass
class DataAnalyzerAgent:
    """Placeholder for DB/schema analysis.

    The callable is responsible for connecting to DBs based on provided DSNs.
    """

    analyze_databases: Callable[[Iterable[str], str], Awaitable[str]]

    @observe_langsmith(name="data_analyzer_agent")
    async def run(self, sources: List[ContextSource], query: str) -> str:
        dbs = [s.path for s in sources if s.type == ContextSourceType.DATABASE]
        if not dbs:
            return ""
        analysis = await self.analyze_databases(dbs, query)
        return f"# Database Findings\n\n{analysis}"


@dataclass
class MemoryRetrieverAgent:
    """Retrieve additional memory/context from memory store (Chroma)."""

    retrieve_memory: Callable[[str, str], Awaitable[str]]

    @observe_langsmith(name="memory_retriever_agent")
    async def run(self, sources: List[ContextSource], query: str) -> str:
        if not any(s.type == ContextSourceType.MEMORY for s in sources):
            return ""
        tasks = [
            self.retrieve_memory(src.path, query)
            for src in sources
            if src.type == ContextSourceType.MEMORY
        ]
        combined = await asyncio.gather(*tasks)
        text = "\n\n".join([c for c in combined if c])
        if not text:
            return ""
        return f"# Memory Findings\n\n{text}"


@dataclass
class SynthesizerAgent:
    """Combine all exploration results into a single markdown document."""

    @observe_langsmith(name="synthesizer_agent")
    def run(self, parts: List[str], query: str) -> str:
        non_empty = [p for p in parts if p.strip()]
        header = f"# Research Summary\n\nQuery: {query}\n\n"
        body = "\n\n".join(non_empty)
        return header + body


@dataclass
class MultiAgentCoordinator:
    """Coordinate specialized sub-agents based on a ContextSpecification."""

    file_agent: FileExplorerAgent
    link_agent: LinkCrawlerAgent
    data_agent: DataAnalyzerAgent
    memory_agent: MemoryRetrieverAgent
    synth_agent: SynthesizerAgent

    @classmethod
    def default(cls) -> "MultiAgentCoordinator":
        """Create a coordinator with no-op but structurally correct agents.

        The default version is intentionally conservative: it avoids real I/O
        and simply echoes high-level information. This is ideal for unit tests
        and can be swapped out in production.
        """

        async def read_paths(paths: Iterable[str]) -> str:
            listed = ", ".join(paths)
            return f"Examined code/docs at: {listed}"

        async def fetch_urls(urls: Iterable[str]) -> str:
            listed = ", ".join(urls)
            return f"Fetched documentation from: {listed}"

        async def analyze_databases(dbs: Iterable[str], query: str) -> str:
            dsns = ", ".join(dbs)
            return f"Considered database(s): {dsns} for query: {query}"

        async def retrieve_memory(identifier: str, query: str) -> str:
            return f"Retrieved memory context for '{identifier}' and query '{query}'."

        return cls(
            file_agent=FileExplorerAgent(read_paths=read_paths),
            link_agent=LinkCrawlerAgent(fetch_urls=fetch_urls),
            data_agent=DataAnalyzerAgent(analyze_databases=analyze_databases),
            memory_agent=MemoryRetrieverAgent(retrieve_memory=retrieve_memory),
            synth_agent=SynthesizerAgent(),
        )

    @classmethod
    def production(
        cls,
        mem0_wrapper: Optional[Any] = None,
    ) -> "MultiAgentCoordinator":
        """Create a coordinator with real I/O for production use.

        Args:
            mem0_wrapper: Optional memory manager instance for memory retrieval.
                          If None, memory agent will be a no-op.
                          Note: Parameter name kept for backward compatibility.
        """

        async def read_paths(paths: Iterable[str]) -> str:
            async def read_single_path(path_str: str) -> str:
                path = Path(path_str)
                if not path.exists():
                    return f"Path not found: {path_str}"

                if path.is_file():
                    try:
                        content = await asyncio.to_thread(path.read_text, encoding="utf-8", errors="ignore")
                        if len(content) > 50000:
                            content = content[:50000] + "\n\n[... truncated ...]"
                        return f"## File: {path_str}\n\n```\n{content}\n```"
                    except Exception as e:
                        return f"Error reading {path_str}: {e}"

                elif path.is_dir():
                    try:
                        def walk_dir(p: Path) -> List[str]:
                            files = []
                            for root, dirs, filenames in os.walk(p):
                                # Skip hidden dirs and common ignore patterns
                                dirs[:] = [d for d in dirs if not d.startswith(".")]
                                for filename in filenames:
                                    if filename.startswith("."):
                                        continue
                                    filepath = Path(root) / filename
                                    files.append(str(filepath.relative_to(p)))
                            return files

                        files = await asyncio.to_thread(walk_dir, path)
                        file_list = "\n".join(files[:100])
                        if len(files) > 100:
                            file_list += f"\n... and {len(files) - 100} more files"
                        return f"## Directory: {path_str}\n\nFiles:\n{file_list}"
                    except Exception as e:
                        return f"Error reading directory {path_str}: {e}"

                return ""

            tasks = [read_single_path(path_str) for path_str in paths]
            results = await asyncio.gather(*tasks)
            return "\n\n".join(results)

        async def fetch_urls(urls: Iterable[str]) -> str:
            client = httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            )

            async def fetch_single_url(url: str) -> str:
                cache_key = ("url_fetch", url)
                cached_content = await get_cached("url_fetch", cache_key)
                if cached_content is not None:
                    return cached_content
                
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    content = response.text
                    if len(content) > 50000:
                        content = content[:50000] + "\n\n[... truncated ...]"
                    result = f"## URL: {url}\n\n```\n{content}\n```"
                    await set_cached("url_fetch", cache_key, result, ttl=1800)
                    return result
                except httpx.RequestError as e:
                    return f"Error fetching {url}: Network error - {e}"
                except httpx.HTTPStatusError as e:
                    return f"Error fetching {url}: HTTP {e.response.status_code}"
                except Exception as e:
                    return f"Error fetching {url}: {e}"

            try:
                tasks = [fetch_single_url(url) for url in urls]
                results = await asyncio.gather(*tasks)
                return "\n\n".join(results)
            finally:
                await client.aclose()

        async def analyze_databases(dbs: Iterable[str], query: str) -> str:
            async def analyze_single_db(dsn: str) -> str:
                try:
                    async_dsn = dsn.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
                    async_dsn = async_dsn.replace("postgresql://", "postgresql+asyncpg://")
                    
                    engine: AsyncEngine = create_async_engine(
                        async_dsn,
                        connect_args={"command_timeout": 5},
                        pool_pre_ping=True,
                    )

                    async with engine.begin() as conn:
                        inspector = inspect(engine.sync_engine)
                        tables = inspector.get_table_names()
                        
                        if not tables:
                            return f"## Database: {dsn}\n\nNo tables found."

                        schema_info = []
                        for table_name in tables[:20]:
                            columns = inspector.get_columns(table_name)
                            col_info = ", ".join([f"{c['name']} ({c['type']})" for c in columns[:10]])
                            schema_info.append(f"- **{table_name}**: {col_info}")

                        result = (
                            f"## Database: {dsn}\n\n"
                            f"Query context: {query}\n\n"
                            f"Tables ({len(tables)}):\n" + "\n".join(schema_info)
                        )
                    
                    await engine.dispose()
                    return result
                except Exception as e:
                    return f"Error analyzing database {dsn}: {e}"

            tasks = [analyze_single_db(dsn) for dsn in dbs]
            results = await asyncio.gather(*tasks)
            return "\n\n".join(results)

        async def retrieve_memory(identifier: str, query: str) -> str:
            if mem0_wrapper is None:
                return f"Memory retrieval not configured for '{identifier}'"
            try:
                user_id = identifier if "/" not in identifier else identifier.split("/")[0]
                memories = await mem0_wrapper.search(user_id=user_id, query=query, limit=5)
                if not memories:
                    return f"No relevant memories found for '{identifier}'"
                mem_texts = [m.get("text", "") for m in memories if m.get("text")]
                return "\n\n".join(mem_texts)
            except Exception as e:
                return f"Error retrieving memory: {e}"

        return cls(
            file_agent=FileExplorerAgent(read_paths=read_paths),
            link_agent=LinkCrawlerAgent(fetch_urls=fetch_urls),
            data_agent=DataAnalyzerAgent(analyze_databases=analyze_databases),
            memory_agent=MemoryRetrieverAgent(retrieve_memory=retrieve_memory),
            synth_agent=SynthesizerAgent(),
        )

    @observe_langsmith(name="multi_agent_coordinator")
    async def research_with_context(self, spec: ContextSpecification) -> str:
        """Run all applicable sub-agents in parallel and synthesize their findings."""
        sources = spec.sources
        file_part, link_part, data_part, memory_part = await asyncio.gather(
            self.file_agent.run(sources, spec.query),
            self.link_agent.run(sources, spec.query),
            self.data_agent.run(sources, spec.query),
            self.memory_agent.run(sources, spec.query),
        )

        parts = [file_part, link_part, data_part, memory_part]
        return self.synth_agent.run(parts, query=spec.query)


