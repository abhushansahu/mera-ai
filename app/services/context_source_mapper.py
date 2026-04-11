"""Shared mapping helpers for context source boundary conversions."""

from __future__ import annotations

from typing import List, Optional

from app.core import ContextSource
from app.multi_agent_context_system import ContextSource as CoordinatorContextSource
from app.multi_agent_context_system import ContextSourceType

_SOURCE_TYPE_ALIASES = {
    "FILE": ContextSourceType.FILE,
    "DIRECTORY": ContextSourceType.DIRECTORY,
    "URL": ContextSourceType.URL,
    "API": ContextSourceType.API,
    "DATABASE": ContextSourceType.DATABASE,
    "MEMORY": ContextSourceType.MEMORY,
    "OBSIDIAN": ContextSourceType.OBSIDIAN,
}


def map_context_source_type(source_type: str) -> Optional[ContextSourceType]:
    normalized = (source_type or "").strip().upper()
    return _SOURCE_TYPE_ALIASES.get(normalized)


def to_coordinator_sources(context_sources: Optional[List[ContextSource]]) -> List[CoordinatorContextSource]:
    mapped: List[CoordinatorContextSource] = []
    for src in context_sources or []:
        ctype = map_context_source_type(src.type)
        if ctype is None:
            continue
        mapped.append(CoordinatorContextSource(type=ctype, path=src.path, extra=src.extra))
    return mapped
