import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, START, END
from langfuse.decorators import observe
from sqlalchemy.ext.asyncio import AsyncSession

from app.context_monitor import context_utilization_percent
from app.error_handler import handle_error_with_learning
from app.llm_client import call_openrouter_chat
from app.memory_factory import MemoryManager, get_memory_manager
from app.memory_mem0 import Mem0Wrapper
from app.models import ConversationMessage
from app.multi_agent_context_system import (
    ContextSource,
    ContextSourceType,
    ContextSpecification,
    MultiAgentCoordinator,
)
from app.obsidian_client import ObsidianClient
from app.prompts import RESEARCH_PROMPT, PLAN_PROMPT, IMPLEMENT_PROMPT
from app.review_system import InMemoryReviewStore, ReviewStatus, ReviewTask


class ConversationState(TypedDict):
    user_id: str
    query: str
    model: str
    messages: List[Dict[str, Any]]
    mem0_results: List[Dict[str, Any]]
    obsidian_context: str
    research_output: Optional[str]
    plan_output: Optional[str]
    answer: Optional[str]
    context_utilization: float
    context_sources: List[Dict[str, str]]
    research_review_id: Optional[str]
    plan_review_id: Optional[str]
    research_approved: bool
    plan_approved: bool


def _build_initial_state(user_id: str, query: str, model: str) -> ConversationState:
    return {
        "user_id": user_id,
        "query": query,
        "model": model,
        "messages": [{"role": "user", "content": query}],
        "mem0_results": [],
        "obsidian_context": "",
        "research_output": None,
        "plan_output": None,
        "answer": None,
        "context_utilization": 0.0,
        "context_sources": [],
        "research_review_id": None,
        "plan_review_id": None,
        "research_approved": False,
        "plan_approved": False,
    }


@observe(name="parallel_context_retrieval")
async def _parallel_context_retrieval_node(
    state: ConversationState, memory: MemoryManager, obsidian: ObsidianClient
) -> ConversationState:
    """Retrieve memory and obsidian context in parallel for better performance."""
    memory_task = memory.search(user_id=state["user_id"], query=state["query"], limit=5)
    obsidian_task = obsidian.search(query=state["query"], limit=5)
    
    results, notes = await asyncio.gather(memory_task, obsidian_task)
    
    state["mem0_results"] = results
    snippets = [n.get("content", "") for n in notes]
    state["obsidian_context"] = "\n\n".join(snippets)
    return state


@observe(name="research")
async def _research_node(state: ConversationState, coordinator: Optional[MultiAgentCoordinator]) -> ConversationState:
    """Research phase using multi-sub-agent system when context is specified.

    Falls back to the simpler RPI research prompt if no explicit context sources
    are provided.
    """
    context_sources = state.get("context_sources") or []
    if coordinator is not None and context_sources:
        sources: List[ContextSource] = []
        for src in context_sources:
            type_str = src.get("type")
            path = src.get("path")
            if not type_str or not path:
                continue
            try:
                src_type = ContextSourceType(type_str)
            except ValueError:
                continue
            sources.append(ContextSource(type=src_type, path=path))

        if sources:
            spec = ContextSpecification(query=state["query"], sources=sources)
            research = await coordinator.research_with_context(spec)
            state["research_output"] = research
            return state

    # Fallback path: use memories + Obsidian context only.
    mem_text = "\n".join([m.get("text", "") for m in state["mem0_results"]])

    prompt = RESEARCH_PROMPT.format(
        query=state["query"],
        memories=mem_text,
        obsidian_context=state["obsidian_context"],
    )
    research = await call_openrouter_chat(
        model=state["model"],
        messages=[{"role": "user", "content": prompt}],
    )
    state["research_output"] = research
    return state


@observe(name="research_review")
async def _research_review_node(
    state: ConversationState, review_store: InMemoryReviewStore
) -> ConversationState:
    """Create a review task for research output and wait for approval."""
    research = state.get("research_output")
    if not research:
        state["research_approved"] = True
        return state

    db = state.get("_db")  # type: ignore
    review_id = state.get("research_review_id")
    
    if not review_id:
        task = ReviewTask(
            id=f"research-{state['user_id']}-{hash(state['query']) % 10000}",
            user_id=state["user_id"],
            type="research",
            content=research,
        )
        await review_store.create(task, db)
        state["research_review_id"] = task.id
        await review_store.set_status(task.id, ReviewStatus.APPROVED, db=db)
        state["research_approved"] = True
    else:
        task = await review_store.get(review_id, db)
        if task and task.status == ReviewStatus.APPROVED:
            state["research_approved"] = True
        elif task and task.status == ReviewStatus.REJECTED:
            state["research_approved"] = False

    return state


@observe(name="plan")
async def _plan_node(state: ConversationState) -> ConversationState:
    if not state.get("research_approved", False):
        state["plan_output"] = "Research not approved. Cannot create plan."
        return state

    research = state.get("research_output") or ""
    content = PLAN_PROMPT + "\n\nUSER QUERY:\n" + state["query"] + "\n\nRESEARCH:\n" + research
    plan = await call_openrouter_chat(
        model=state["model"],
        messages=[{"role": "user", "content": content}],
    )
    state["plan_output"] = plan
    return state


@observe(name="plan_review")
async def _plan_review_node(
    state: ConversationState, review_store: InMemoryReviewStore
) -> ConversationState:
    """Create a review task for plan output and wait for approval."""
    plan = state.get("plan_output")
    if not plan:
        state["plan_approved"] = True
        return state

    db = state.get("_db")  # type: ignore
    review_id = state.get("plan_review_id")
    
    if not review_id:
        task = ReviewTask(
            id=f"plan-{state['user_id']}-{hash(state['query']) % 10000}",
            user_id=state["user_id"],
            type="plan",
            content=plan,
        )
        await review_store.create(task, db)
        state["plan_review_id"] = task.id
        await review_store.set_status(task.id, ReviewStatus.APPROVED, db=db)
        state["plan_approved"] = True
    else:
        task = await review_store.get(review_id, db)
        if task and task.status == ReviewStatus.APPROVED:
            state["plan_approved"] = True
        elif task and task.status == ReviewStatus.REJECTED:
            state["plan_approved"] = False

    return state


@observe(name="implement")
async def _implement_node(state: ConversationState) -> ConversationState:
    if not state.get("plan_approved", False):
        state["answer"] = "Plan not approved. Cannot implement."
        return state

    research = state.get("research_output") or ""
    plan = state.get("plan_output") or ""
    content = (
        IMPLEMENT_PROMPT
        + "\n\nUSER QUERY:\n"
        + state["query"]
        + "\n\nRESEARCH:\n"
        + research
        + "\n\nPLAN:\n"
        + plan
    )
    answer = await call_openrouter_chat(
        model=state["model"],
        messages=[{"role": "user", "content": content}],
    )
    state["answer"] = answer
    state["messages"].append({"role": "assistant", "content": answer})
    return state


@observe(name="monitor_context")
def _monitor_context_node(state: ConversationState) -> ConversationState:
    """Compute and store context utilization for observability."""
    utilization = context_utilization_percent(state["messages"])
    state["context_utilization"] = utilization
    return state


@observe(name="mem0_store")
async def _store_mem0_node(state: ConversationState, memory: MemoryManager) -> ConversationState:
    """Store the latest interaction into memory for future retrieval (fire-and-forget)."""
    if not state.get("answer"):
        return state

    asyncio.create_task(
        memory.store(
            user_id=state["user_id"],
            text=f"Q: {state['query']}\nA: {state['answer']}",
            metadata={"source": "unified-assistant"},
        )
    )
    return state


@observe(name="obsidian_update")
async def _update_obsidian_node(state: ConversationState, obsidian: ObsidianClient) -> ConversationState:
    """Write a compact summary of the interaction into Obsidian (fire-and-forget)."""
    if not state.get("answer"):
        return state

    title = f"AI Session - {state['user_id']}"
    content = (
        f"# AI Session\n\n"
        f"## Query\n{state['query']}\n\n"
        f"## Research\n{state.get('research_output') or ''}\n\n"
        f"## Plan\n{state.get('plan_output') or ''}\n\n"
        f"## Answer\n{state['answer']}\n"
    )
    asyncio.create_task(obsidian.create_note(title=title, content=content, tags=["ai-session"]))
    return state


@dataclass
class UnifiedOrchestrator:
    """LangGraph-based orchestrator with Memory + Obsidian + RPI + sub-agents + reviews."""

    memory: MemoryManager = field(default_factory=get_memory_manager)
    obsidian: ObsidianClient = field(default_factory=ObsidianClient)
    coordinator: Optional[MultiAgentCoordinator] = None
    review_store: InMemoryReviewStore = field(default_factory=InMemoryReviewStore)

    def __post_init__(self) -> None:
        if self.coordinator is None:
            # MultiAgentCoordinator expects mem0_wrapper, but we can pass any MemoryManager
            # For now, we'll pass it as mem0_wrapper for backward compatibility
            mem0_wrapper = self.memory if isinstance(self.memory, Mem0Wrapper) else None
            self.coordinator = MultiAgentCoordinator.production(mem0_wrapper=mem0_wrapper)

        graph = StateGraph(ConversationState)

        graph.add_node("parallel_context", lambda s: _parallel_context_retrieval_node(s, self.memory, self.obsidian))
        graph.add_node("research", lambda s: _research_node(s, self.coordinator))
        graph.add_node("research_review", lambda s: _research_review_node(s, self.review_store))
        graph.add_node("plan", _plan_node)
        graph.add_node("plan_review", lambda s: _plan_review_node(s, self.review_store))
        graph.add_node("implement", _implement_node)
        graph.add_node("monitor_context", _monitor_context_node)
        graph.add_node("mem0_store", lambda s: _store_mem0_node(s, self.memory))
        graph.add_node("obsidian_update", lambda s: _update_obsidian_node(s, self.obsidian))

        graph.add_edge(START, "parallel_context")
        graph.add_edge("parallel_context", "research")
        graph.add_edge("research", "research_review")
        graph.add_edge("research_review", "plan")
        graph.add_edge("plan", "plan_review")
        graph.add_edge("plan_review", "implement")
        graph.add_edge("implement", "monitor_context")
        graph.add_edge("monitor_context", "mem0_store")
        graph.add_edge("mem0_store", "obsidian_update")
        graph.add_edge("obsidian_update", END)

        self._app = graph.compile()

    @observe(name="process_query")
    async def process_query(
        self,
        user_id: str,
        query: str,
        preferred_model: Optional[str],
        db: AsyncSession,
        context_sources: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Entry point used by the HTTP API."""
        model = preferred_model or "openai/gpt-4o-mini"
        state = _build_initial_state(user_id=user_id, query=query, model=model)
        if context_sources:
            state["context_sources"] = context_sources
        
        state["_db"] = db  # type: ignore

        try:
            result = await self._app.ainvoke(state)
            for idx, msg in enumerate(result["messages"]):
                db_msg = ConversationMessage(
                    id=f"{user_id}-{idx}",
                    user_id=user_id,
                    role=msg["role"],
                    content=msg["content"],
                    message_metadata={},
                )
                db.add(db_msg)
            await db.commit()
            return result["answer"] or ""
        except Exception as exc:  # noqa: BLE001
            learning = await handle_error_with_learning(
                error=exc,
                user_id=user_id,
                query=query,
                model=model,
                obsidian=self.obsidian,
            )
            return learning["safe_message"]
