"""Core types, protocols, and exceptions for Mera AI."""

from typing import Dict, List, Optional, Protocol

from pydantic import BaseModel, Field

# Type aliases
UserID = str
Query = str

# Data models
class ContextSource(BaseModel):
    type: str = Field(...)
    path: str = Field(...)
    extra: Optional[Dict[str, str]] = Field(default=None)


class Memory(BaseModel):
    text: str = Field(...)
    metadata: Dict[str, str] = Field(default_factory=dict)
    score: Optional[float] = Field(default=None)


class LLMMessage(BaseModel):
    role: str = Field(...)
    content: str = Field(...)


class LLMResponse(BaseModel):
    content: str = Field(...)
    model: str = Field(...)
    metadata: Dict[str, str] = Field(default_factory=dict)


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

# Protocols
class LLMProvider(Protocol):
    async def chat(
        self,
        messages: List[LLMMessage],
        model: str,
        **kwargs,
    ) -> LLMResponse:
        ...


class MemoryManager(Protocol):
    async def store(
        self,
        user_id: UserID,
        text: str,
        metadata: Optional[dict] = None,
    ) -> None:
        ...

    async def search(
        self,
        user_id: UserID,
        query: str,
        limit: int = 5,
    ) -> List[Memory]:
        ...


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

# Exceptions
class MeraAIError(Exception):
    """Base exception for all Mera AI errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}


class ConfigurationError(MeraAIError):
    """Raised when there's a configuration error."""
    pass


class SpaceError(MeraAIError):
    """Raised when there's an error related to spaces."""
    pass


class SpaceNotFoundError(SpaceError):
    """Raised when a requested space is not found."""
    pass


class SpaceBudgetExceededError(SpaceError):
    """Raised when a space's token budget is exceeded."""
    pass


class MemoryError(MeraAIError):
    """Raised when there's an error with memory operations."""
    pass


class LLMError(MeraAIError):
    """Raised when there's an error with LLM operations."""
    pass


class ObsidianError(MeraAIError):
    """Raised when there's an error with Obsidian operations."""
    pass


class IndexError(MeraAIError):
    """Raised when there's an error with indexing operations."""
    pass


class WorkflowError(MeraAIError):
    """Raised when there's an error in workflow execution."""
    pass
