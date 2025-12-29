"""Unified LangChain-based orchestrator replacing DomainOrchestrator."""

from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.chroma import ChromaMemoryAdapter
from app.adapters.openrouter import OpenRouterLLMAdapter
from app.core.orchestrator import Orchestrator, WorkflowResult
from app.core.types import ContextSource, Query, UserID
from app.infrastructure.config.settings import get_settings
from app.infrastructure.observability import observe_langsmith
from app.langchain_chains import (
    create_research_chain,
    create_plan_chain,
    create_implement_chain,
)
from app.memory_factory import get_memory_manager
from app.multi_agent_context_system import MultiAgentCoordinator
from app.obsidian_client import ObsidianClient
from app.models import ConversationMessage


@dataclass
class LangChainUnifiedOrchestrator:
    """Unified LangChain-based orchestrator with Research → Plan → Implement workflow.
    
    This orchestrator uses LangChain Agents and Chains to replace the custom RPIWorkflow.
    It maintains the same interface as DomainOrchestrator for compatibility.
    """

    llm: Optional[OpenRouterLLMAdapter] = None
    memory: Optional[ChromaMemoryAdapter] = None
    obsidian: Optional[ObsidianClient] = None
    coordinator: Optional[MultiAgentCoordinator] = None

    def __post_init__(self) -> None:
        """Initialize components if not provided."""
        settings = get_settings()

        if self.llm is None:
            self.llm = OpenRouterLLMAdapter()

        if self.memory is None:
            self.memory = ChromaMemoryAdapter(
                host=settings.chroma_host,
                port=settings.chroma_port,
                collection_name=settings.chroma_collection_name,
                persist_directory=settings.chroma_persist_dir,
            )

        if self.obsidian is None:
            self.obsidian = ObsidianClient()

        if self.coordinator is None:
            self.coordinator = MultiAgentCoordinator.production(mem0_wrapper=self.memory)

    @observe_langsmith(name="process_query")
    async def process_query(
        self,
        user_id: UserID,
        query: Query,
        model: Optional[str] = None,
        context_sources: Optional[List[ContextSource]] = None,
        db: Optional[AsyncSession] = None,
        **kwargs,
    ) -> WorkflowResult:
        """Process a user query through Research → Plan → Implement workflow.
        
        Args:
            user_id: User identifier
            query: User's query
            model: LLM model to use (optional)
            context_sources: Optional list of context sources
            db: Database session for storing conversation
            **kwargs: Additional arguments
            
        Returns:
            WorkflowResult with answer, research, plan, and metadata
        """
        settings = get_settings()
        model = model or settings.default_model

        try:
            # Convert context_sources to dict format for chains
            context_sources_dict = None
            if context_sources:
                context_sources_dict = [
                    {"type": cs.type, "path": cs.path, **(cs.extra or {})}
                    for cs in context_sources
                ]

            # Research phase - uses LangChain Agent with retrieval tools
            research_chain = create_research_chain(
                user_id=user_id,
                model=model,
                memory=self.memory,
                obsidian=self.obsidian,
                coordinator=self.coordinator,
            )
            research_result = await research_chain.ainvoke({
                "query": query,
                "context_sources": context_sources_dict or [],
            })
            research = research_result.get("research", "")

            # Plan phase - uses LangChain LLM planner
            plan_chain = create_plan_chain(model=model)
            plan_result = await plan_chain.ainvoke({
                "query": query,
                "research": research,
            })
            plan = plan_result.get("plan", "")

            # Implement phase - uses LangChain tool-calling agent
            implement_chain = create_implement_chain(model=model)
            implement_result = await implement_chain.ainvoke({
                "query": query,
                "research": research,
                "plan": plan,
            })
            answer = implement_result.get("answer", "")

            # Store conversation in database if provided
            if db:
                await self._store_conversation(
                    user_id=user_id,
                    query=query,
                    answer=answer,
                    db=db,
                )

            # Store in memory (fire-and-forget)
            await self._store_memory(user_id=user_id, query=query, answer=answer)

            return WorkflowResult(
                answer=answer,
                research=research,
                plan=plan,
                metadata={"model": model},
            )
        except Exception as e:
            return WorkflowResult(
                answer=f"I encountered an error processing your query: {str(e)}",
                metadata={"error": str(e)},
            )

    async def _store_conversation(
        self,
        user_id: UserID,
        query: Query,
        answer: str,
        db: AsyncSession,
    ) -> None:
        """Store conversation in database."""
        messages = [
            {"role": "user", "content": query},
            {"role": "assistant", "content": answer},
        ]

        for idx, msg in enumerate(messages):
            db_msg = ConversationMessage(
                id=f"{user_id}-{idx}",
                user_id=user_id,
                role=msg["role"],
                content=msg["content"],
                message_metadata={},
            )
            db.add(db_msg)
        await db.commit()

    async def _store_memory(
        self,
        user_id: UserID,
        query: Query,
        answer: str,
    ) -> None:
        """Store interaction in memory (fire-and-forget)."""
        import asyncio
        asyncio.create_task(
            self.memory.store(
                user_id=user_id,
                text=f"Q: {query}\nA: {answer}",
                metadata={"source": "unified-assistant"},
            )
        )
