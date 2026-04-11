"""Versioned API contract models for migration-safe interoperability."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

CONTRACT_VERSION = "v1"


class ContextSourceContract(BaseModel):
    type: Literal["FILE", "DIRECTORY", "URL", "API", "DATABASE", "MEMORY", "OBSIDIAN"]
    path: str
    extra: Optional[Dict[str, Any]] = None


class ObsidianContextEventContract(BaseModel):
    event_id: Optional[str] = None
    event_type: Literal["open", "click", "selection", "navigate"]
    note_path: str
    note_title: Optional[str] = None
    selection: Optional[str] = None
    clicked_target: Optional[str] = None
    cursor_line: Optional[int] = None
    event_ts_ms: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatRequestContract(BaseModel):
    user_id: Optional[str] = None
    query: str
    model: Optional[str] = None
    provider: Optional[str] = None
    context_sources: Optional[List[ContextSourceContract]] = None
    space_id: Optional[str] = None
    thread_id: Optional[str] = None


class ChatResponseContract(BaseModel):
    user_id: str
    answer: str
    research: Optional[str] = None
    plan: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StatusResponseContract(BaseModel):
    status: str
    required_api_keys: Dict[str, str]
    database_connected: bool
    database_error: Optional[str] = None
    optional_services: Dict[str, bool]
    contract_version: str = CONTRACT_VERSION


class FeatureFlagsContract(BaseModel):
    threading: bool
    per_message_model: bool
    secure_provider_settings: bool
    obsidian_advanced: bool
    rpi_compact_layout: bool
    obsidian_event_sync: bool

