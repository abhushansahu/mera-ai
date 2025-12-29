"""Observability: LangSmith tracing, logging, and metrics."""

import logging
import os
import sys
from functools import wraps
from time import time
from typing import Any, Callable, Dict, Optional

from langsmith import Client, traceable
from pythonjsonlogger import jsonlogger

from app.infrastructure.config.settings import get_settings

# LangSmith
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
    """Decorator for LangSmith tracing.

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
        _configure_langsmith_env()
        trace_name = name or func.__name__
        traced_func = traceable(name=trace_name, **kwargs)(func)
        return traced_func
    return decorator

# Logging
def setup_logging(level: str = "INFO") -> None:
    """Setup JSON logging."""
    log_handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.addHandler(log_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)

# Metrics
_metrics: Dict[str, list] = {}


def record_metric(name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
    """Record a metric."""
    if name not in _metrics:
        _metrics[name] = []
    _metrics[name].append({"value": value, "tags": tags or {}, "timestamp": time()})


def get_metrics(name: Optional[str] = None) -> Dict:
    """Get metrics."""
    if name:
        return {name: _metrics.get(name, [])}
    return _metrics


def clear_metrics() -> None:
    """Clear all metrics."""
    _metrics.clear()


def track_latency(metric_name: str):
    """Decorator to track function latency."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                latency = time() - start
                record_metric(f"{metric_name}.latency", latency)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                latency = time() - start
                record_metric(f"{metric_name}.latency", latency)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
