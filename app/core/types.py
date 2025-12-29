from typing import Dict, List, Optional

from pydantic import BaseModel, Field

UserID = str
Query = str


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
