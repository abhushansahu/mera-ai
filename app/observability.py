"""Minimal observability: LangSmith tracing (optional)."""

import os
from functools import wraps
from typing import Any, Callable, Optional

from app.config import get_settings

_langsmith_enabled: Optional[bool] = None

def _is_langsmith_enabled() -> bool:
    global _langsmith_enabled
    if _langsmith_enabled is None:
        settings = get_settings()
        if settings.langsmith_api_key:
            os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
            os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
            os.environ["LANGCHAIN_API_URL"] = settings.langsmith_api_url
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            try:
                from langsmith import traceable
                _langsmith_enabled = True
            except ImportError:
                _langsmith_enabled = False
        else:
            _langsmith_enabled = False
    return _langsmith_enabled

def is_langsmith_enabled() -> bool:
    """Check if LangSmith is enabled."""
    return _is_langsmith_enabled()

def observe_langsmith(name: Optional[str] = None, **kwargs: Any) -> Callable:
    """Decorator for LangSmith tracing (no-op if disabled)."""
    def decorator(func: Callable) -> Callable:
        if _is_langsmith_enabled():
            try:
                from langsmith import traceable
                trace_name = name or func.__name__
                return traceable(name=trace_name, **kwargs)(func)
            except ImportError:
                pass
        return func
    return decorator
