"""LangChain chains for Research, Plan, and Implement phases."""

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from app.langchain_retrievers import ChromaRetriever, ObsidianRetriever
from app.langchain_tools import create_tools_from_coordinator
from app.llm_client import call_openrouter_chat
from app.multi_agent_context_system import MultiAgentCoordinator
from app.obsidian_client import ObsidianClient
from app.prompts import RESEARCH_PROMPT, PLAN_PROMPT, IMPLEMENT_PROMPT
from app.memory_factory import MemoryManager, get_memory_manager


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


def create_research_chain(
    user_id: str,
    model: str = "openai/gpt-4o-mini",
    memory: Optional[MemoryManager] = None,
    obsidian: Optional[ObsidianClient] = None,
    coordinator: Optional[MultiAgentCoordinator] = None,
) -> RunnablePassthrough:
    """Create a LangChain chain for the research phase.
    
    Args:
        user_id: User identifier
        model: LLM model to use
        memory: MemoryManager instance (defaults to factory)
        obsidian: ObsidianClient instance (defaults to new instance)
        coordinator: MultiAgentCoordinator for context sources (optional)
    
    Returns:
        LangChain chain that takes a query and returns research output
    """
    memory = memory or get_memory_manager()
    obsidian = obsidian or ObsidianClient()
    
    # Create retrievers
    chroma_retriever = ChromaRetriever(memory=memory, user_id=user_id, k=5)
    obsidian_retriever = ObsidianRetriever(obsidian=obsidian, k=5)
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a research assistant that synthesizes information from multiple sources."),
        ("user", RESEARCH_PROMPT),
    ])
    
    # Create LLM
    llm = OpenRouterLLM(model=model)
    
    async def research_workflow(inputs: dict) -> dict:
        """Workflow that retrieves context and generates research."""
        query = inputs.get("query", "")
        context_sources = inputs.get("context_sources", [])
        
        # Retrieve from memory and Obsidian
        memory_docs = await chroma_retriever._aget_relevant_documents(query)
        obsidian_docs = await obsidian_retriever._aget_relevant_documents(query)
        
        # Format memory context
        memories_text = "\n".join([doc.page_content for doc in memory_docs])
        
        # Format Obsidian context
        obsidian_text = "\n\n".join([doc.page_content for doc in obsidian_docs])
        
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
        
        # Fallback: use simple prompt with retrieved context
        formatted_prompt = RESEARCH_PROMPT.format(
            query=query,
            memories=memories_text,
            obsidian_context=obsidian_text,
        )
        
        research = await llm.ainvoke([{"role": "user", "content": formatted_prompt}])
        return {"research": research}
    
    return RunnablePassthrough() | research_workflow


def create_plan_chain(
    model: str = "openai/gpt-4o-mini",
) -> RunnablePassthrough:
    """Create a LangChain chain for the plan phase.
    
    Args:
        model: LLM model to use
    
    Returns:
        LangChain chain that takes research and query, returns plan
    """
    llm = OpenRouterLLM(model=model)
    
    async def plan_workflow(inputs: dict) -> dict:
        """Workflow that generates a plan from research."""
        query = inputs.get("query", "")
        research = inputs.get("research", "")
        
        content = PLAN_PROMPT + "\n\nUSER QUERY:\n" + query + "\n\nRESEARCH:\n" + research
        plan = await llm.ainvoke([{"role": "user", "content": content}])
        return {"plan": plan}
    
    return RunnablePassthrough() | plan_workflow


def create_implement_chain(
    model: str = "openai/gpt-4o-mini",
) -> RunnablePassthrough:
    """Create a LangChain chain for the implement phase.
    
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
