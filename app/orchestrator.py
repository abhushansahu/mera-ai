"""CrewAI orchestrator with Research → Plan → Implement workflow."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, List, Optional

import tiktoken
from crewai import Crew, Process
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.chroma import ChromaMemoryAdapter
from app.adapters.openrouter import OpenRouterLLMAdapter
from app.adapters.obsidian import ObsidianClient
from app.config import get_settings
from app.core import ContextSource, LLMMessage, Orchestrator, Query, UserID, WorkflowResult
from app.crewai import create_agents_for_space, create_tasks_for_workflow
from app.models import ConversationMessage
from app.multi_agent_context_system import MultiAgentCoordinator
from app.observability import observe_langsmith
from app.spaces import SpaceConfig, SpaceManager

logger = logging.getLogger(__name__)


def _estimate_tokens(content: Any) -> int:
    """Estimate token count using tiktoken."""
    try:
        enc = tiktoken.encoding_for_model("gpt-4o")
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(str(content)))


def _get_memory_for_space(space_config: Optional[SpaceConfig] = None) -> ChromaMemoryAdapter:
    """Get memory manager for a space."""
    settings = get_settings()
    collection_name = space_config.mem0_collection_name if space_config else settings.chroma_collection_name
    return ChromaMemoryAdapter(
        host=settings.chroma_host,
        port=settings.chroma_port,
        collection_name=collection_name,
        persist_directory=settings.chroma_persist_dir,
    )


class OpenRouterLLMWrapper(BaseChatModel):
    """LangChain-compatible wrapper for OpenRouter LLM adapter."""
    
    def __init__(self, model: str = "openai/gpt-4o-mini", **kwargs):
        super().__init__(**kwargs)
        self.model = model
        self.adapter = OpenRouterLLMAdapter()
    
    @property
    def _llm_type(self) -> str:
        return "openrouter"
    
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        import asyncio
        return asyncio.run(self._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs))
    
    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        llm_messages = []
        for msg in messages:
            if hasattr(msg, 'type'):
                role_map = {'human': 'user', 'user': 'user', 'ai': 'assistant', 'assistant': 'assistant', 'system': 'system'}
                role = role_map.get(msg.type, 'user')
            elif hasattr(msg, 'role'):
                role = msg.role
            else:
                role = 'user'
            content = msg.content if hasattr(msg, 'content') else str(msg)
            llm_messages.append(LLMMessage(role=role, content=content))
        
        response = await self.adapter.chat(messages=llm_messages, model=self.model, **kwargs)
        ai_message = AIMessage(content=response.content)
        generation = ChatGeneration(message=ai_message, generation_info={"model": response.model, **response.metadata})
        return ChatResult(generations=[[generation]])


@dataclass
class CrewAIOrchestrator:
    """CrewAI-based orchestrator with Research → Plan → Implement workflow."""

    llm: Optional[OpenRouterLLMAdapter] = None
    memory: Optional[ChromaMemoryAdapter] = None
    obsidian: Optional[ObsidianClient] = None
    coordinator: Optional[MultiAgentCoordinator] = None

    def __post_init__(self) -> None:
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
        """Process a user query through Research → Plan → Implement workflow."""
        settings = get_settings()
        model = model or settings.default_model

        space_memory = self.memory
        space_obsidian = self.obsidian
        space_coordinator = self.coordinator
        space_schema = None
        tokens_used = 0

        if space_manager:
            try:
                space_config = space_manager.get_current_space()
                space_schema = space_config.postgres_schema
                usage = await space_manager.get_space_usage(space_config.space_id)
                remaining = usage.get_budget_remaining(space_config)
                if remaining < 10_000:
                    return WorkflowResult(
                        answer=f"Space budget exceeded. Only {remaining:,} tokens remaining.",
                        metadata={"error": "budget_exceeded", "remaining": remaining},
                    )
                space_memory = _get_memory_for_space(space_config)
                space_obsidian = ObsidianClient(vault_path=space_config.obsidian_vault_path)
                space_coordinator = MultiAgentCoordinator.production(mem0_wrapper=space_memory)
                if space_config.preferred_model:
                    model = space_config.preferred_model
            except RuntimeError:
                pass

        try:
            # Retrieve context directly from adapters
            memories = await space_memory.search(user_id=user_id, query=query, limit=5)
            memories_text = "\n".join([m.text for m in memories])
            
            obsidian_text = ""
            try:
                obsidian_results = await space_obsidian.search(query=query, limit=5)
                obsidian_text = "\n\n".join([r.get("content", "") for r in obsidian_results])
            except Exception as e:
                logger.warning(f"Obsidian retrieval failed: {e}")

            llm = OpenRouterLLMWrapper(model=model)
            researcher, planner, implementer = create_agents_for_space(
                memory=space_memory, obsidian=space_obsidian, coordinator=space_coordinator, user_id=user_id, llm=llm, verbose=False
            )
            
            research_task, plan_task, implement_task = create_tasks_for_workflow(
                researcher_agent=researcher, planner_agent=planner, implementer_agent=implementer,
                query=query, memories=memories_text, obsidian_context=obsidian_text
            )
            
            crew = Crew(agents=[researcher, planner, implementer], tasks=[research_task, plan_task, implement_task], process=Process.sequential, verbose=False)
            result = await asyncio.to_thread(crew.kickoff)
            
            # Extract outputs
            research = str(research_task.output.raw) if hasattr(research_task, 'output') and research_task.output and hasattr(research_task.output, 'raw') else (str(research_task.output) if hasattr(research_task, 'output') and research_task.output else "")
            plan = str(plan_task.output.raw) if hasattr(plan_task, 'output') and plan_task.output and hasattr(plan_task.output, 'raw') else (str(plan_task.output) if hasattr(plan_task, 'output') and plan_task.output else "")
            answer = str(implement_task.output.raw) if hasattr(implement_task, 'output') and implement_task.output and hasattr(implement_task.output, 'raw') else (str(implement_task.output) if hasattr(implement_task, 'output') and implement_task.output else "")
            
            if not answer:
                if hasattr(result, 'tasks_output') and result.tasks_output and len(result.tasks_output) >= 3:
                    research = str(result.tasks_output[0]) if len(result.tasks_output) > 0 else research
                    plan = str(result.tasks_output[1]) if len(result.tasks_output) > 1 else plan
                    answer = str(result.tasks_output[2]) if len(result.tasks_output) > 2 else ""
                elif hasattr(result, 'raw') and result.raw:
                    answer = str(result.raw)
                elif isinstance(result, str):
                    answer = result
                else:
                    answer = str(result)
            
            if db:
                if space_schema:
                    await db.execute(text(f'SET search_path TO "{space_schema}", public'))
                messages = [
                    ConversationMessage(id=f"{user_id}-{hash(query)}-0", user_id=user_id, role="user", content=query, message_metadata={}),
                    ConversationMessage(id=f"{user_id}-{hash(query)}-1", user_id=user_id, role="assistant", content=answer, message_metadata={}),
                ]
                db.add_all(messages)
                await db.commit()

            asyncio.create_task(space_memory.store(user_id=user_id, text=f"Q: {query}\nA: {answer}", metadata={"source": "crewai-assistant"}))

            if space_manager:
                try:
                    space_config = space_manager.get_current_space()
                    total_tokens = _estimate_tokens(query) + _estimate_tokens(research) + _estimate_tokens(plan) + _estimate_tokens(answer)
                    await space_manager.update_space_usage(
                        space_id=space_config.space_id, tokens_used=total_tokens, api_calls_used=3, cost_usd=(total_tokens / 1000) * 0.015
                    )
                    tokens_used = total_tokens
                except Exception as e:
                    logger.warning(f"Failed to track token usage: {e}")

            return WorkflowResult(answer=answer, research=research, plan=plan, metadata={"model": model, "tokens_used": tokens_used})
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return WorkflowResult(answer=f"I encountered an error processing your query: {str(e)}", metadata={"error": str(e)})
