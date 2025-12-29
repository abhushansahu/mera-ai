from typing import Dict, List, Optional, Protocol

from pydantic import BaseModel, Field

from app.core.types import ContextSource, Query, UserID


class WorkflowState(BaseModel):
    user_id: UserID
    query: Query
    model: str
    context_sources: List[ContextSource] = Field(default_factory=list)
    research: Optional[str] = None
    plan: Optional[str] = None
    answer: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


class WorkflowResult(BaseModel):
    answer: str
    research: Optional[str] = None
    plan: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


class Orchestrator(Protocol):
    async def process_query(
        self,
        user_id: UserID,
        query: Query,
        model: Optional[str] = None,
        context_sources: Optional[List[ContextSource]] = None,
        **kwargs,
    ) -> WorkflowResult:
        ...
