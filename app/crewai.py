"""CrewAI tools, agents, and tasks for Research → Plan → Implement workflow."""

import asyncio
from pathlib import Path
from typing import List, Optional

from crewai import Agent, Task
from crewai.tools import tool

from app.adapters.chroma import ChromaMemoryAdapter
from app.adapters.obsidian import ObsidianClient
from app.multi_agent_context_system import (
    ContextSource,
    ContextSourceType,
    FileExplorerAgent,
    LinkCrawlerAgent,
    DataAnalyzerAgent,
    MemoryRetrieverAgent,
    MultiAgentCoordinator,
)

# Prompts
RESEARCH_PROMPT = """TASK: A good group of people are understanding the user's request deeply.

USER QUERY:
{query}

MEMORIES:
{memories}

OBSIDIAN CONTEXT:
{obsidian_context}

OUTPUT: A concise markdown document named 'research.md' with sections:
1. Problem Statement
2. Key Context and Constraints
3. Relevant Prior Information
4. Open Questions / Gaps
5. Recommended High-Level Approach

Be factual and avoid speculation."""

PLAN_PROMPT = """A good group of people are creating an implementation plan.

INPUT:
- USER QUERY
- RESEARCH DOCUMENT

Create a markdown document named 'plan.md' with:
1. Step-by-step sequence of actions
2. Data or state that must be read or written
3. Any external tools or services that should be called
4. Testing and validation steps
5. Clear success criteria

The plan should be explicit enough that a less-capable model can follow it reliably."""

IMPLEMENT_PROMPT = """A good group of people are executing a pre-written plan exactly.

INPUT:
- USER QUERY
- RESEARCH DOCUMENT
- IMPLEMENTATION PLAN

TASK:
- Follow the plan step-by-step.
- Do not introduce unrelated work.
- When unsure, state the uncertainty explicitly.

OUTPUT:
- Final answer for the user
- Brief summary of what you did"""


# Tools
class ChromaMemoryTool:
    """CrewAI tool wrapper for ChromaMemoryAdapter."""

    def __init__(self, memory: ChromaMemoryAdapter, user_id: str):
        self.memory = memory
        self.user_id = user_id

    def search_memory(self, query: str, limit: int = 5) -> str:
        results = asyncio.run(self.memory.search(user_id=self.user_id, query=query, limit=limit))
        if not results:
            return f"No relevant memories found for query: {query}"
        return "\n\n".join([
            f"Memory {i+1} (score: {m.score:.2f}):\n{m.text}"
            for i, m in enumerate(results)
        ])

    def to_crewai_tool(self):
        @tool("memory_search")
        def memory_search_tool(query: str, limit: int = 5) -> str:
            """Search the user's memory store for relevant past conversations, stored knowledge, or context. Use this to retrieve information from previous interactions."""
            return self.search_memory(query, limit)
        return memory_search_tool


class ObsidianTool:
    """CrewAI tool wrapper for ObsidianClient."""

    def __init__(self, obsidian: ObsidianClient):
        self.obsidian = obsidian

    def search_obsidian(self, query: str, limit: int = 5) -> str:
        results = asyncio.run(self.obsidian.search(query=query, limit=limit))
        if not results:
            return f"No relevant notes found in Obsidian vault for query: {query}"
        return "\n\n".join([
            f"Note: {r.get('path', 'Unknown')}\n{r.get('content', '')[:500]}..."
            if len(r.get('content', '')) > 500
            else f"Note: {r.get('path', 'Unknown')}\n{r.get('content', '')}"
            for r in results
        ])

    def to_crewai_tool(self):
        @tool("obsidian_search")
        def obsidian_search_tool(query: str, limit: int = 5) -> str:
            """Search the Obsidian knowledge base vault for relevant notes, documentation, or stored knowledge. Use this to retrieve information from the user's personal knowledge base."""
            return self.search_obsidian(query, limit)
        return obsidian_search_tool


class FileExplorerCrewAITool:
    """CrewAI tool wrapper for FileExplorerAgent."""

    def __init__(self, file_agent: FileExplorerAgent):
        self.file_agent = file_agent

    def explore_files(self, paths: str) -> str:
        path_list = [p.strip() for p in paths.replace("\n", ",").split(",") if p.strip()]
        sources = [
            ContextSource(
                type=ContextSourceType.FILE if Path(p).is_file() else ContextSourceType.DIRECTORY,
                path=p,
            )
            for p in path_list
        ]
        return asyncio.run(self.file_agent.run(sources, query=""))

    def to_crewai_tool(self):
        @tool("file_explorer")
        def file_explorer_tool(paths: str) -> str:
            """Explore local files and directories. Use this tool to read file contents or list directory structures. Input should be a list of file or directory paths (comma-separated)."""
            return self.explore_files(paths)
        return file_explorer_tool


class LinkCrawlerCrewAITool:
    """CrewAI tool wrapper for LinkCrawlerAgent."""

    def __init__(self, link_agent: LinkCrawlerAgent):
        self.link_agent = link_agent

    def crawl_links(self, urls: str) -> str:
        url_list = [u.strip() for u in urls.replace("\n", ",").split(",") if u.strip()]
        sources = [
            ContextSource(
                type=ContextSourceType.URL if u.startswith("http") else ContextSourceType.API,
                path=u,
            )
            for u in url_list
        ]
        return asyncio.run(self.link_agent.run(sources, query=""))

    def to_crewai_tool(self):
        @tool("link_crawler")
        def link_crawler_tool(urls: str) -> str:
            """Fetch and summarize content from URLs or API endpoints. Use this tool to retrieve documentation, web pages, or API responses. Input should be a list of URLs or API endpoints (comma-separated)."""
            return self.crawl_links(urls)
        return link_crawler_tool


class DataAnalyzerCrewAITool:
    """CrewAI tool wrapper for DataAnalyzerAgent."""

    def __init__(self, data_agent: DataAnalyzerAgent, query_context: str = ""):
        self.data_agent = data_agent
        self.query_context = query_context

    def analyze_database(self, dsn: str) -> str:
        sources = [ContextSource(type=ContextSourceType.DATABASE, path=dsn)]
        return asyncio.run(self.data_agent.run(sources, query=self.query_context or ""))

    def to_crewai_tool(self):
        @tool("data_analyzer")
        def data_analyzer_tool(dsn: str) -> str:
            """Analyze database schemas and structures. Use this tool to explore database tables, columns, and relationships. Input should be a database connection string (DSN)."""
            return self.analyze_database(dsn)
        return data_analyzer_tool


class MemoryRetrieverCrewAITool:
    """CrewAI tool wrapper for MemoryRetrieverAgent."""

    def __init__(self, memory_agent: MemoryRetrieverAgent):
        self.memory_agent = memory_agent

    def retrieve_memory(self, identifier_and_query: str) -> str:
        parts = identifier_and_query.split(":", 1)
        if len(parts) == 2:
            identifier, query = parts
        else:
            identifier = "default"
            query = parts[0]
        sources = [ContextSource(type=ContextSourceType.MEMORY, path=identifier)]
        return asyncio.run(self.memory_agent.run(sources, query=query))

    def to_crewai_tool(self):
        @tool("memory_retriever")
        def memory_retriever_tool(identifier_and_query: str) -> str:
            """Retrieve relevant memories from the memory store. Use this tool to search for past conversations, stored knowledge, or user context. Input should be 'identifier:query' or just 'query' (uses default identifier)."""
            return self.retrieve_memory(identifier_and_query)
        return memory_retriever_tool


def create_crewai_tools(
    memory: Optional[ChromaMemoryAdapter] = None,
    obsidian: Optional[ObsidianClient] = None,
    coordinator: Optional[MultiAgentCoordinator] = None,
    user_id: str = "default",
) -> list:
    """Create CrewAI tools from adapters and coordinator."""
    tools = []
    if memory:
        tools.append(ChromaMemoryTool(memory=memory, user_id=user_id).to_crewai_tool())
    if obsidian:
        tools.append(ObsidianTool(obsidian=obsidian).to_crewai_tool())
    if coordinator:
        if coordinator.file_agent:
            tools.append(FileExplorerCrewAITool(file_agent=coordinator.file_agent).to_crewai_tool())
        if coordinator.link_agent:
            tools.append(LinkCrawlerCrewAITool(link_agent=coordinator.link_agent).to_crewai_tool())
        if coordinator.data_agent:
            tools.append(DataAnalyzerCrewAITool(data_agent=coordinator.data_agent).to_crewai_tool())
        if coordinator.memory_agent:
            tools.append(MemoryRetrieverCrewAITool(memory_agent=coordinator.memory_agent).to_crewai_tool())
    return tools


# Agents
def create_researcher_agent(tools: List, llm=None, verbose: bool = False) -> Agent:
    """Create Researcher Agent for gathering context."""
    return Agent(
        role="Research Assistant",
        goal="Gather comprehensive context from memory, Obsidian vault, files, URLs, and databases to understand the user's query deeply",
        backstory=(
            "You are an expert at synthesizing information from multiple sources. "
            "You excel at finding relevant context from memory stores, knowledge bases, "
            "code repositories, documentation, and databases. Your research is thorough "
            "and you always identify key information, constraints, and open questions."
        ),
        tools=tools,
        verbose=verbose,
        max_iter=5,
        allow_delegation=False,
        llm=llm,
    )


def create_planner_agent(llm=None, verbose: bool = False) -> Agent:
    """Create Planner Agent for creating implementation plans."""
    return Agent(
        role="Implementation Planner",
        goal="Create detailed, step-by-step implementation plans that break down complex tasks into actionable steps",
        backstory=(
            "You are an expert at breaking down complex tasks into actionable steps. "
            "You create clear, detailed plans that specify what needs to be done, "
            "what data or state is required, which tools to use, how to test, and "
            "what success looks like. Your plans are explicit enough that they can "
            "be followed reliably by others."
        ),
        tools=[],
        verbose=verbose,
        max_iter=3,
        allow_delegation=False,
        llm=llm,
    )


def create_implementer_agent(tools: List, llm=None, verbose: bool = False) -> Agent:
    """Create Implementer Agent for executing plans."""
    return Agent(
        role="Implementation Executor",
        goal="Execute plans step-by-step and provide final answers to the user",
        backstory=(
            "You are an expert at following plans precisely and delivering results. "
            "You execute implementation plans step-by-step, using tools when needed "
            "to read code, fetch documentation, or gather information. You stay focused "
            "on the plan and don't introduce unrelated work. When uncertain, you state "
            "your uncertainty explicitly."
        ),
        tools=tools,
        verbose=verbose,
        max_iter=5,
        allow_delegation=False,
        llm=llm,
    )


def create_agents_for_space(
    memory: Optional[ChromaMemoryAdapter] = None,
    obsidian: Optional[ObsidianClient] = None,
    coordinator: Optional[MultiAgentCoordinator] = None,
    user_id: str = "default",
    llm=None,
    verbose: bool = False,
) -> tuple[Agent, Agent, Agent]:
    """Create all three agents (Researcher, Planner, Implementer) for a space."""
    all_tools = create_crewai_tools(memory=memory, obsidian=obsidian, coordinator=coordinator, user_id=user_id)
    researcher = create_researcher_agent(tools=all_tools, llm=llm, verbose=verbose)
    planner = create_planner_agent(llm=llm, verbose=verbose)
    implementer_tools = [tool for tool in all_tools if tool.name in ["file_explorer", "link_crawler"]]
    implementer = create_implementer_agent(tools=implementer_tools, llm=llm, verbose=verbose)
    return researcher, planner, implementer


# Tasks
def create_research_task(researcher_agent: Agent, query: str, memories: str = "", obsidian_context: str = "") -> Task:
    """Create Research Task."""
    description = RESEARCH_PROMPT.format(
        query=query,
        memories=memories or "No memories found.",
        obsidian_context=obsidian_context or "No Obsidian context found.",
    )
    return Task(
        description=description,
        agent=researcher_agent,
        expected_output=(
            "A markdown document with Problem Statement, Key Context and Constraints, "
            "Relevant Prior Information, Open Questions / Gaps, and Recommended High-Level Approach"
        ),
    )


def create_plan_task(planner_agent: Agent, query: str, research_output: str) -> Task:
    """Create Plan Task."""
    description = PLAN_PROMPT + "\n\nUSER QUERY:\n" + query + "\n\nRESEARCH:\n" + research_output
    return Task(
        description=description,
        agent=planner_agent,
        expected_output=(
            "A markdown document with step-by-step actions, data requirements, "
            "tools needed, testing steps, and success criteria"
        ),
        context=[],
    )


def create_implement_task(implementer_agent: Agent, query: str, research_output: str, plan_output: str) -> Task:
    """Create Implement Task."""
    description = (
        IMPLEMENT_PROMPT
        + "\n\nUSER QUERY:\n"
        + query
        + "\n\nRESEARCH:\n"
        + research_output
        + "\n\nPLAN:\n"
        + plan_output
    )
    return Task(
        description=description,
        agent=implementer_agent,
        expected_output="Final answer for the user with brief summary of actions taken",
        context=[],
    )


def create_tasks_for_workflow(
    researcher_agent: Agent,
    planner_agent: Agent,
    implementer_agent: Agent,
    query: str,
    memories: str = "",
    obsidian_context: str = "",
) -> tuple[Task, Task, Task]:
    """Create all three tasks (Research, Plan, Implement) for a workflow."""
    research_task = create_research_task(researcher_agent=researcher_agent, query=query, memories=memories, obsidian_context=obsidian_context)
    plan_task = create_plan_task(planner_agent=planner_agent, query=query, research_output="")
    plan_task.context = [research_task]
    implement_task = create_implement_task(implementer_agent=implementer_agent, query=query, research_output="", plan_output="")
    implement_task.context = [research_task, plan_task]
    return research_task, plan_task, implement_task
