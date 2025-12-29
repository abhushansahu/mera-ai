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
from app.memory_factory import get_memory_manager, get_memory_manager_for_space
from app.multi_agent_context_system import MultiAgentCoordinator
from app.obsidian_client import ObsidianClient
from app.models import ConversationMessage
from app.spaces.space_manager import SpaceManager


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
        space_manager: Optional[SpaceManager] = None,
        **kwargs,
    ) -> WorkflowResult:
        """Process a user query through Research → Plan → Implement workflow.
        
        Args:
            user_id: User identifier
            query: User's query
            model: LLM model to use (optional)
            context_sources: Optional list of context sources
            db: Database session for storing conversation
            space_manager: Optional space manager for space-scoped operations
            **kwargs: Additional arguments
            
        Returns:
            WorkflowResult with answer, research, plan, and metadata
        """
        settings = get_settings()
        model = model or settings.default_model

        # Space-aware setup
        space_memory = self.memory
        space_obsidian = self.obsidian
        space_coordinator = self.coordinator
        space_schema = None
        tokens_used = 0

        if space_manager:
            try:
                space_config = space_manager.get_current_space()
                space_schema = space_config.postgres_schema

                # Check budget before processing
                usage = await space_manager.get_space_usage(space_config.space_id)
                remaining = usage.get_budget_remaining(space_config)
                if remaining < 10_000:
                    return WorkflowResult(
                        answer=f"Space budget exceeded. Only {remaining:,} tokens remaining. Please upgrade your plan or wait for the next billing cycle.",
                        metadata={"error": "budget_exceeded", "remaining": remaining},
                    )

                # Use space-specific memory
                space_memory = get_memory_manager_for_space(space_config)

                # Use space-specific Obsidian
                space_obsidian = ObsidianClient(vault_path=space_config.obsidian_vault_path)

                # Use space-specific coordinator with space memory
                space_coordinator = MultiAgentCoordinator.production(mem0_wrapper=space_memory)

                # Use space preferred model if available
                if space_config.preferred_model:
                    model = space_config.preferred_model
            except RuntimeError:
                # No space selected, use defaults
                pass

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
                memory=space_memory,
                obsidian=space_obsidian,
                coordinator=space_coordinator,
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
                    space_schema=space_schema,
                )

            # Store in memory (fire-and-forget) using space-specific memory
            await self._store_memory(
                user_id=user_id,
                query=query,
                answer=answer,
                memory=space_memory,
            )

            # Track token usage if space manager provided
            # Note: Actual token tracking would need to be extracted from LLM responses
            # For now, we'll estimate or track via metadata if available
            if space_manager:
                try:
                    space_config = space_manager.get_current_space()
                    # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
                    estimated_tokens = len(query + answer + research + plan) // 4
                    # Cost estimation (rough: $0.015 per 1K tokens for GPT-4o-mini)
                    estimated_cost = (estimated_tokens / 1000) * 0.015
                    await space_manager.update_space_usage(
                        space_id=space_config.space_id,
                        tokens_used=estimated_tokens,
                        api_calls_used=3,  # research, plan, implement
                        cost_usd=estimated_cost,
                    )
                except RuntimeError:
                    pass

            return WorkflowResult(
                answer=answer,
                research=research,
                plan=plan,
                metadata={"model": model, "tokens_used": tokens_used},
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
        space_schema: Optional[str] = None,
    ) -> None:
        """Store conversation in database, optionally in space-specific schema."""
        from sqlalchemy import text
        from app.db import engine

        messages = [
            {"role": "user", "content": query},
            {"role": "assistant", "content": answer},
        ]

        # If space schema specified, set search_path
        if space_schema:
            async with engine.connect() as conn:
                # Set schema for this transaction
                await conn.execute(text(f'SET search_path TO "{space_schema}", public'))
                await conn.commit()

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
        memory: Optional[ChromaMemoryAdapter] = None,
    ) -> None:
        """Store interaction in memory (fire-and-forget)."""
        import asyncio
        memory_to_use = memory or self.memory
        asyncio.create_task(
            memory_to_use.store(
                user_id=user_id,
                text=f"Q: {query}\nA: {answer}",
                metadata={"source": "unified-assistant"},
            )
        )
