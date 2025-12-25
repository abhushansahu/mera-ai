"""LangChain-based orchestrator to replace UnifiedOrchestrator."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langfuse.decorators import observe
from sqlalchemy.ext.asyncio import AsyncSession

from app.langchain_chains import (
    create_research_chain,
    create_plan_chain,
    create_implement_chain,
)
from app.memory_factory import MemoryManager, get_memory_manager
from app.multi_agent_context_system import MultiAgentCoordinator
from app.obsidian_client import ObsidianClient
from app.review_system import InMemoryReviewStore, ReviewStatus, ReviewTask
from app.models import ConversationMessage
from app.error_handler import handle_error_with_learning


@dataclass
class LangChainOrchestrator:
    """LangChain-based orchestrator with Memory + Obsidian + RPI + sub-agents + reviews.
    
    This orchestrator uses LangChain chains instead of LangGraph for the RPI workflow.
    """

    memory: MemoryManager = field(default_factory=get_memory_manager)
    obsidian: ObsidianClient = field(default_factory=ObsidianClient)
    coordinator: Optional[MultiAgentCoordinator] = None
    review_store: InMemoryReviewStore = field(default_factory=InMemoryReviewStore)

    def __post_init__(self) -> None:
        """Initialize the coordinator if not provided."""
        if self.coordinator is None:
            from app.memory_mem0 import Mem0Wrapper
            # For backward compatibility, pass Mem0Wrapper if available
            mem0_wrapper = self.memory if isinstance(self.memory, Mem0Wrapper) else None
            self.coordinator = MultiAgentCoordinator.production(mem0_wrapper=mem0_wrapper)

    @observe(name="process_query")
    async def process_query(
        self,
        user_id: str,
        query: str,
        preferred_model: Optional[str],
        db: AsyncSession,
        context_sources: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Entry point used by the HTTP API.
        
        Args:
            user_id: User identifier
            query: User's query
            preferred_model: Preferred LLM model (optional)
            db: Database session
            context_sources: Optional list of context sources
        
        Returns:
            Final answer string
        """
        model = preferred_model or "openai/gpt-4o-mini"
        
        try:
            # Research phase
            research = await self._research_phase(
                user_id=user_id,
                query=query,
                model=model,
                context_sources=context_sources,
                db=db,
            )
            
            # Plan phase
            plan = await self._plan_phase(
                user_id=user_id,
                query=query,
                research=research,
                model=model,
                db=db,
            )
            
            # Implement phase
            answer = await self._implement_phase(
                query=query,
                research=research,
                plan=plan,
                model=model,
            )
            
            # Store conversation in database
            await self._store_conversation(user_id=user_id, query=query, answer=answer, db=db)
            
            # Store in memory (fire-and-forget)
            await self._store_memory(user_id=user_id, query=query, answer=answer)
            
            # Update Obsidian (fire-and-forget)
            await self._update_obsidian(user_id=user_id, query=query, research=research, plan=plan, answer=answer)
            
            return answer
            
        except Exception as exc:  # noqa: BLE001
            learning = await handle_error_with_learning(
                error=exc,
                user_id=user_id,
                query=query,
                model=model,
                obsidian=self.obsidian,
            )
            return learning["safe_message"]

    @observe(name="research_phase")
    async def _research_phase(
        self,
        user_id: str,
        query: str,
        model: str,
        context_sources: Optional[List[Dict[str, str]]],
        db: AsyncSession,
    ) -> str:
        """Execute research phase with review."""
        # Create research chain
        research_chain = create_research_chain(
            user_id=user_id,
            model=model,
            memory=self.memory,
            obsidian=self.obsidian,
            coordinator=self.coordinator,
        )
        
        # Execute research
        result = await research_chain.ainvoke({
            "query": query,
            "context_sources": context_sources or [],
        })
        research = result.get("research", "")
        
        # Review research
        research_approved = await self._review_research(
            user_id=user_id,
            query=query,
            research=research,
            db=db,
        )
        
        if not research_approved:
            return "Research not approved. Cannot proceed."
        
        return research

    @observe(name="plan_phase")
    async def _plan_phase(
        self,
        user_id: str,
        query: str,
        research: str,
        model: str,
        db: AsyncSession,
    ) -> str:
        """Execute plan phase with review."""
        # Create plan chain
        plan_chain = create_plan_chain(model=model)
        
        # Execute plan
        result = await plan_chain.ainvoke({
            "query": query,
            "research": research,
        })
        plan = result.get("plan", "")
        
        # Review plan
        plan_approved = await self._review_plan(
            user_id=user_id,
            query=query,
            plan=plan,
            db=db,
        )
        
        if not plan_approved:
            return "Plan not approved. Cannot proceed."
        
        return plan

    @observe(name="implement_phase")
    async def _implement_phase(
        self,
        query: str,
        research: str,
        plan: str,
        model: str,
    ) -> str:
        """Execute implement phase."""
        # Create implement chain
        implement_chain = create_implement_chain(model=model)
        
        # Execute implementation
        result = await implement_chain.ainvoke({
            "query": query,
            "research": research,
            "plan": plan,
        })
        
        return result.get("answer", "")

    async def _review_research(
        self,
        user_id: str,
        query: str,
        research: str,
        db: AsyncSession,
    ) -> bool:
        """Review research output."""
        if not research:
            return True
        
        task = ReviewTask(
            id=f"research-{user_id}-{hash(query) % 10000}",
            user_id=user_id,
            type="research",
            content=research,
        )
        await self.review_store.create(task, db)
        await self.review_store.set_status(task.id, ReviewStatus.APPROVED, db=db)
        return True

    async def _review_plan(
        self,
        user_id: str,
        query: str,
        plan: str,
        db: AsyncSession,
    ) -> bool:
        """Review plan output."""
        if not plan:
            return True
        
        task = ReviewTask(
            id=f"plan-{user_id}-{hash(query) % 10000}",
            user_id=user_id,
            type="plan",
            content=plan,
        )
        await self.review_store.create(task, db)
        await self.review_store.set_status(task.id, ReviewStatus.APPROVED, db=db)
        return True

    async def _store_conversation(
        self,
        user_id: str,
        query: str,
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
        user_id: str,
        query: str,
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

    async def _update_obsidian(
        self,
        user_id: str,
        query: str,
        research: str,
        plan: str,
        answer: str,
    ) -> None:
        """Update Obsidian vault (fire-and-forget)."""
        import asyncio
        title = f"AI Session - {user_id}"
        content = (
            f"# AI Session\n\n"
            f"## Query\n{query}\n\n"
            f"## Research\n{research}\n\n"
            f"## Plan\n{plan}\n\n"
            f"## Answer\n{answer}\n"
        )
        asyncio.create_task(
            self.obsidian.create_note(title=title, content=content, tags=["ai-session"])
        )
