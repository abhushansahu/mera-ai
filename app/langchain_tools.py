"""LangChain tool wrappers for multi-agent sub-agents."""

from typing import Optional

from langchain_core.tools import BaseTool
from pydantic import Field

from app.multi_agent_context_system import (
    ContextSource,
    ContextSourceType,
    FileExplorerAgent,
    LinkCrawlerAgent,
    DataAnalyzerAgent,
    MemoryRetrieverAgent,
)


class FileExplorerTool(BaseTool):
    """LangChain tool wrapper for FileExplorerAgent."""

    name: str = "file_explorer"
    description: str = (
        "Explore local files and directories. "
        "Use this tool to read file contents or list directory structures. "
        "Input should be a list of file or directory paths."
    )
    file_agent: FileExplorerAgent = Field(exclude=True)

    def __init__(self, file_agent: FileExplorerAgent, **kwargs):
        super().__init__(file_agent=file_agent, **kwargs)

    def _run(self, paths: str) -> str:
        """Synchronous run method (not used, but required by BaseTool)."""
        raise NotImplementedError("Use async_run instead")

    async def _arun(self, paths: str) -> str:
        """Asynchronous run method."""
        import asyncio
        from pathlib import Path
        
        # Parse paths (can be comma-separated or newline-separated)
        path_list = [p.strip() for p in paths.replace("\n", ",").split(",") if p.strip()]
        
        # Convert to ContextSource objects
        sources = [
            ContextSource(
                type=ContextSourceType.FILE if Path(p).is_file() else ContextSourceType.DIRECTORY,
                path=p,
            )
            for p in path_list
        ]
        
        return await self.file_agent.run(sources, query="")

    def _run_sync(self, paths: str) -> str:
        """Synchronous wrapper (for compatibility)."""
        import asyncio
        return asyncio.run(self._arun(paths))


class LinkCrawlerTool(BaseTool):
    """LangChain tool wrapper for LinkCrawlerAgent."""

    name: str = "link_crawler"
    description: str = (
        "Fetch and summarize content from URLs or API endpoints. "
        "Use this tool to retrieve documentation, web pages, or API responses. "
        "Input should be a list of URLs or API endpoints."
    )
    link_agent: LinkCrawlerAgent = Field(exclude=True)

    def __init__(self, link_agent: LinkCrawlerAgent, **kwargs):
        super().__init__(link_agent=link_agent, **kwargs)

    def _run(self, urls: str) -> str:
        """Synchronous run method (not used, but required by BaseTool)."""
        raise NotImplementedError("Use async_run instead")

    async def _arun(self, urls: str) -> str:
        """Asynchronous run method."""
        # Parse URLs (can be comma-separated or newline-separated)
        url_list = [u.strip() for u in urls.replace("\n", ",").split(",") if u.strip()]
        
        # Convert to ContextSource objects
        sources = [
            ContextSource(
                type=ContextSourceType.URL if u.startswith("http") else ContextSourceType.API,
                path=u,
            )
            for u in url_list
        ]
        
        return await self.link_agent.run(sources, query="")

    def _run_sync(self, urls: str) -> str:
        """Synchronous wrapper (for compatibility)."""
        import asyncio
        return asyncio.run(self._arun(urls))


class DataAnalyzerTool(BaseTool):
    """LangChain tool wrapper for DataAnalyzerAgent."""

    name: str = "data_analyzer"
    description: str = (
        "Analyze database schemas and structures. "
        "Use this tool to explore database tables, columns, and relationships. "
        "Input should be a database connection string (DSN) and an optional query context."
    )
    data_agent: DataAnalyzerAgent = Field(exclude=True)
    query_context: Optional[str] = Field(default="", exclude=True)

    def __init__(self, data_agent: DataAnalyzerAgent, query_context: str = "", **kwargs):
        super().__init__(data_agent=data_agent, query_context=query_context, **kwargs)

    def _run(self, dsn: str) -> str:
        """Synchronous run method (not used, but required by BaseTool)."""
        raise NotImplementedError("Use async_run instead")

    async def _arun(self, dsn: str) -> str:
        """Asynchronous run method."""
        sources = [
            ContextSource(
                type=ContextSourceType.DATABASE,
                path=dsn,
            )
        ]
        
        return await self.data_agent.run(sources, query=self.query_context or "")

    def _run_sync(self, dsn: str) -> str:
        """Synchronous wrapper (for compatibility)."""
        import asyncio
        return asyncio.run(self._arun(dsn))


class MemoryRetrieverTool(BaseTool):
    """LangChain tool wrapper for MemoryRetrieverAgent."""

    name: str = "memory_retriever"
    description: str = (
        "Retrieve relevant memories from the memory store. "
        "Use this tool to search for past conversations, stored knowledge, or user context. "
        "Input should be a memory identifier (user_id or user_id/path) and a search query."
    )
    memory_agent: MemoryRetrieverAgent = Field(exclude=True)

    def __init__(self, memory_agent: MemoryRetrieverAgent, **kwargs):
        super().__init__(memory_agent=memory_agent, **kwargs)

    def _run(self, identifier_and_query: str) -> str:
        """Synchronous run method (not used, but required by BaseTool)."""
        raise NotImplementedError("Use async_run instead")

    async def _arun(self, identifier_and_query: str) -> str:
        """Asynchronous run method.
        
        Expected format: "identifier:query" or just "query" (uses default identifier)
        """
        parts = identifier_and_query.split(":", 1)
        if len(parts) == 2:
            identifier, query = parts
        else:
            identifier = "default"
            query = parts[0]
        
        sources = [
            ContextSource(
                type=ContextSourceType.MEMORY,
                path=identifier,
            )
        ]
        
        return await self.memory_agent.run(sources, query=query)

    def _run_sync(self, identifier_and_query: str) -> str:
        """Synchronous wrapper (for compatibility)."""
        import asyncio
        return asyncio.run(self._arun(identifier_and_query))


def create_tools_from_coordinator(coordinator) -> list[BaseTool]:
    """Create LangChain tools from a MultiAgentCoordinator.
    
    Args:
        coordinator: MultiAgentCoordinator instance
    
    Returns:
        List of LangChain tools
    """
    tools = []
    
    if coordinator.file_agent:
        tools.append(FileExplorerTool(file_agent=coordinator.file_agent))
    
    if coordinator.link_agent:
        tools.append(LinkCrawlerTool(link_agent=coordinator.link_agent))
    
    if coordinator.data_agent:
        tools.append(DataAnalyzerTool(data_agent=coordinator.data_agent))
    
    if coordinator.memory_agent:
        tools.append(MemoryRetrieverTool(memory_agent=coordinator.memory_agent))
    
    return tools
