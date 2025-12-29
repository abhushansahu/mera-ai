"""LangSmith client for observability and tracing."""

import os
from functools import wraps
from typing import Any, Callable, Optional

from langsmith import Client, traceable

from app.infrastructure.config.settings import get_settings

_langsmith_client: Optional[Client] = None
_langsmith_initialization_error: Optional[str] = None


def _configure_langsmith_env() -> None:
    """Configure environment variables for LangSmith."""
    settings = get_settings()
    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    if settings.langsmith_project:
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    if settings.langsmith_api_url:
        os.environ["LANGCHAIN_API_URL"] = settings.langsmith_api_url
    if settings.langsmith_tracing_v2:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"


def get_langsmith_client() -> Optional[Client]:
    """Get or create LangSmith client instance."""
    global _langsmith_client, _langsmith_initialization_error

    settings = get_settings()
    if not settings.langsmith_api_key:
        return None

    if _langsmith_client is not None:
        return _langsmith_client

    if _langsmith_initialization_error is not None:
        return None

    try:
        _configure_langsmith_env()
        _langsmith_client = Client(
            api_key=settings.langsmith_api_key,
            api_url=settings.langsmith_api_url or "https://api.smith.langchain.com",
        )
        return _langsmith_client
    except Exception as e:
        _langsmith_initialization_error = f"LangSmith initialization failed: {e}"
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"LangSmith observability disabled due to initialization error: {e}")
        return None


def is_langsmith_enabled() -> bool:
    """Check if LangSmith is enabled and configured."""
    settings = get_settings()
    if not settings.langsmith_api_key:
        return False
    client = get_langsmith_client()
    return client is not None


def get_langsmith_error() -> Optional[str]:
    """Get LangSmith initialization error if any."""
    return _langsmith_initialization_error


def observe_langsmith(name: Optional[str] = None, **kwargs: Any) -> Callable:
    """Decorator for LangSmith tracing, similar to Langfuse @observe.

    Usage:
        @observe_langsmith(name="my_function")
        async def my_function():
            ...

    Args:
        name: Name of the trace/run
        **kwargs: Additional arguments passed to traceable decorator

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        # Configure LangSmith environment
        _configure_langsmith_env()

        # Determine trace name
        trace_name = name or func.__name__

        # Use traceable decorator directly
        # traceable handles both sync and async functions
        traced_func = traceable(name=trace_name, **kwargs)(func)

        return traced_func

    return decorator
