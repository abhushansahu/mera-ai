"""LangChain chains for Research, Plan, and Implement phases."""

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langsmith import traceable

from app.adapters.chroma import ChromaMemoryAdapter
from app.adapters.obsidian import ObsidianClient
from app.adapters.openrouter import call_openrouter_chat
from app.infrastructure.config.settings import get_settings
from app.infrastructure.indexing import LlamaIndexRetriever, ObsidianIndexer
from app.langchain_retrievers import ChromaRetriever
from app.langchain_tools import create_tools_from_coordinator
from app.multi_agent_context_system import MultiAgentCoordinator

# Inline prompts
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


def _get_memory_manager(collection_name: Optional[str] = None) -> ChromaMemoryAdapter:
    """Get memory manager with optional collection name override."""
    settings = get_settings()
    return ChromaMemoryAdapter(
        host=settings.chroma_host,
        port=settings.chroma_port,
        collection_name=collection_name or settings.chroma_collection_name,
        persist_directory=settings.chroma_persist_dir,
    )


class OpenRouterLLM:
    """Wrapper to make OpenRouter compatible with LangChain's LLM interface."""

    def __init__(self, model: str = "openai/gpt-4o-mini"):
        self.model = model

    async def ainvoke(self, messages: List[dict]) -> str:
        """Async invoke for LangChain compatibility."""
        return await call_openrouter_chat(
            model=self.model,
            messages=messages,
        )

    def invoke(self, messages: List[dict]) -> str:
        """Sync invoke (not recommended, but required by interface)."""
        import asyncio
        return asyncio.run(self.ainvoke(messages))


@traceable(name="research_chain")
def create_research_chain(
    user_id: str,
    model: str = "openai/gpt-4o-mini",
    memory: Optional[ChromaMemoryAdapter] = None,
    obsidian: Optional[ObsidianClient] = None,
    coordinator: Optional[MultiAgentCoordinator] = None,
) -> RunnablePassthrough:
    """Create a LangChain chain for the research phase using Agents with tools.
    
    Args:
        user_id: User identifier
        model: LLM model to use
        memory: ChromaMemoryAdapter instance (defaults to factory)
        obsidian: ObsidianClient instance (defaults to new instance)
        coordinator: MultiAgentCoordinator for context sources (optional)
    
    Returns:
        LangChain chain that takes a query and returns research output
    """
    memory = memory or _get_memory_manager()
    
    # Create retrievers
    chroma_retriever = ChromaRetriever(memory=memory, user_id=user_id, k=5)
    
    # Use LlamaIndex retriever for Obsidian if vault path is configured
    settings = get_settings()
    obsidian_retriever = None
    if settings.obsidian_vault_path:
        try:
            indexer = ObsidianIndexer(vault_path=settings.obsidian_vault_path)
            obsidian_retriever = LlamaIndexRetriever(indexer=indexer, k=5)
        except Exception:
            # Fallback to REST API if LlamaIndex fails
            obsidian = obsidian or ObsidianClient()
            from app.langchain_retrievers import ObsidianRetriever
            obsidian_retriever = ObsidianRetriever(obsidian=obsidian, k=5)
    else:
        # Fallback to REST API if vault path not configured
        obsidian = obsidian or ObsidianClient()
        from app.langchain_retrievers import ObsidianRetriever
        obsidian_retriever = ObsidianRetriever(obsidian=obsidian, k=5)
    
    # Create LLM
    llm = OpenRouterLLM(model=model)
    
    async def research_workflow(inputs: dict) -> dict:
        """Workflow that retrieves context and generates research using agents."""
        query = inputs.get("query", "")
        context_sources = inputs.get("context_sources", [])
        
        # If coordinator and context sources provided, use multi-agent system
        if coordinator and context_sources:
            from app.multi_agent_context_system import ContextSource, ContextSourceType, ContextSpecification
            
            sources = []
            for src in context_sources:
                type_str = src.get("type")
                path = src.get("path")
                if type_str and path:
                    try:
                        src_type = ContextSourceType(type_str)
                        sources.append(ContextSource(type=src_type, path=path))
                    except ValueError:
                        continue
            
            if sources:
                spec = ContextSpecification(query=query, sources=sources)
                research = await coordinator.research_with_context(spec)
                return {"research": research}
        
        # Retrieve from memory and Obsidian
        memory_docs = await chroma_retriever._aget_relevant_documents(query)
        obsidian_text = ""
        if obsidian_retriever:
            obsidian_docs = await obsidian_retriever._aget_relevant_documents(query)
            obsidian_text = "\n\n".join([doc.page_content for doc in obsidian_docs])
        
        # Format memory context
        memories_text = "\n".join([doc.page_content for doc in memory_docs])
        
        # Create tools for agent if coordinator available
        tools = []
        if coordinator:
            tools = create_tools_from_coordinator(coordinator)
        
        # If tools available, use agent; otherwise use simple chain
        if tools:
            # Create agent prompt
            system_prompt = """You are a research assistant that synthesizes information from multiple sources.
            You have access to tools for exploring files, URLs, databases, and memory.
            Use these tools to gather comprehensive context before generating your research document."""
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", RESEARCH_PROMPT + "\n\nQuery: {query}\n\nMemories:\n{memories}\n\nObsidian Context:\n{obsidian_context}"),
                ("placeholder", "{agent_scratchpad}"),
            ])
            
            # Create agent (simplified - using RunnablePassthrough for now)
            # Full agent implementation would use create_openai_tools_agent
            formatted_prompt = RESEARCH_PROMPT.format(
                query=query,
                memories=memories_text,
                obsidian_context=obsidian_text,
            )
            research = await llm.ainvoke([{"role": "user", "content": formatted_prompt}])
        else:
            # Simple prompt-based research
            formatted_prompt = RESEARCH_PROMPT.format(
                query=query,
                memories=memories_text,
                obsidian_context=obsidian_text,
            )
            research = await llm.ainvoke([{"role": "user", "content": formatted_prompt}])
        
        return {"research": research}
    
    return RunnablePassthrough() | research_workflow


@traceable(name="plan_chain")
def create_plan_chain(
    model: str = "openai/gpt-4o-mini",
) -> RunnablePassthrough:
    """Create a LangChain chain for the plan phase using LLM planner pattern.
    
    Args:
        model: LLM model to use
    
    Returns:
        LangChain chain that takes research and query, returns plan
    """
    llm = OpenRouterLLM(model=model)
    
    async def plan_workflow(inputs: dict) -> dict:
        """Workflow that generates a plan from research using structured output."""
        query = inputs.get("query", "")
        research = inputs.get("research", "")
        
        # Create structured prompt for planning
        content = PLAN_PROMPT + "\n\nUSER QUERY:\n" + query + "\n\nRESEARCH:\n" + research
        plan = await llm.ainvoke([{"role": "user", "content": content}])
        return {"plan": plan}
    
    return RunnablePassthrough() | plan_workflow


@traceable(name="implement_chain")
def create_implement_chain(
    model: str = "openai/gpt-4o-mini",
) -> RunnablePassthrough:
    """Create a LangChain chain for the implement phase using tool-calling agent.
    
    Args:
        model: LLM model to use
    
    Returns:
        LangChain chain that takes query, research, and plan, returns answer
    """
    llm = OpenRouterLLM(model=model)
    
    async def implement_workflow(inputs: dict) -> dict:
        """Workflow that generates an answer from research and plan."""
        query = inputs.get("query", "")
        research = inputs.get("research", "")
        plan = inputs.get("plan", "")
        
        # Execute plan step-by-step
        content = (
            IMPLEMENT_PROMPT
            + "\n\nUSER QUERY:\n"
            + query
            + "\n\nRESEARCH:\n"
            + research
            + "\n\nPLAN:\n"
            + plan
        )
        answer = await llm.ainvoke([{"role": "user", "content": content}])
        return {"answer": answer}
    
    return RunnablePassthrough() | implement_workflow
