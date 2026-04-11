"""Versioned API contract models for migration-safe interoperability."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

CONTRACT_VERSION = "v1"


class ContextSourceContract(BaseModel):
    type: str
    path: str
    extra: Optional[Dict[str, str]] = None


class ChatRequestContract(BaseModel):
    user_id: str
    query: str
    model: Optional[str] = None
    context_sources: Optional[List[ContextSourceContract]] = None
    space_id: Optional[str] = None


class ChatResponseContract(BaseModel):
    user_id: str
    answer: str
    research: Optional[str] = None
    plan: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    contract_version: str = CONTRACT_VERSION


class StatusResponseContract(BaseModel):
    status: str
    required_api_keys: Dict[str, str]
    database_connected: bool
    database_error: Optional[str] = None
    optional_services: Dict[str, bool]
    contract_version: str = CONTRACT_VERSION

