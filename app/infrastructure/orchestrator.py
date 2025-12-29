from dataclasses import dataclass
from typing import List, Optional

from app.infrastructure.observability import observe_langsmith
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.chroma import ChromaMemoryAdapter
from app.adapters.openrouter import OpenRouterLLMAdapter
from app.core.orchestrator import Orchestrator, WorkflowResult
from app.core.types import ContextSource, Query, UserID
from app.domain.workflow import RPIWorkflow
from app.infrastructure.config.settings import get_settings
from app.models import ConversationMessage


@dataclass
class DomainOrchestrator:
    llm: Optional[OpenRouterLLMAdapter] = None
    memory: Optional[ChromaMemoryAdapter] = None
    workflow: Optional[RPIWorkflow] = None

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
        
        if self.workflow is None:
            self.workflow = RPIWorkflow(llm=self.llm, memory=self.memory)

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
        settings = get_settings()
        model = model or settings.default_model
        
        try:
            research = await self.workflow.research(
                user_id=user_id,
                query=query,
                model=model,
                context_sources=context_sources,
            )
            
            plan = await self.workflow.plan(
                query=query,
                research=research,
                model=model,
            )
            
            implement = await self.workflow.implement(
                query=query,
                research=research,
                plan=plan,
                model=model,
            )
            
            if db:
                await self._store_conversation(
                    user_id=user_id,
                    query=query,
                    answer=implement.answer,
                    db=db,
                )
            
            await self._store_memory(user_id=user_id, query=query, answer=implement.answer)
            
            return WorkflowResult(
                answer=implement.answer,
                research=research.content,
                plan=plan.content,
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
        import asyncio
        asyncio.create_task(
            self.memory.store(
                user_id=user_id,
                text=f"Q: {query}\nA: {answer}",
                metadata={"source": "unified-assistant"},
            )
        )
