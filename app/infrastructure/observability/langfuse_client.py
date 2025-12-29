import os
from typing import Optional

from langfuse import Langfuse

from app.infrastructure.config.settings import get_settings

_langfuse_client: Optional[Langfuse] = None
_langfuse_initialization_error: Optional[str] = None


def _set_langfuse_dummy_env_vars() -> None:
    settings = get_settings()
    if "NEXT_PUBLIC_API_URL" not in os.environ:
        os.environ["NEXT_PUBLIC_API_URL"] = settings.langfuse_host or "http://localhost:3000"
    if "NEXT_RUNTIME" not in os.environ:
        os.environ["NEXT_RUNTIME"] = "nodejs"
    if "NODE_ENV" not in os.environ:
        os.environ["NODE_ENV"] = "production"


def get_langfuse_client() -> Optional[Langfuse]:
    global _langfuse_client, _langfuse_initialization_error
    
    settings = get_settings()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    
    if _langfuse_client is not None:
        return _langfuse_client
    
    if _langfuse_initialization_error is not None:
        return None
    
    try:
        _set_langfuse_dummy_env_vars()
        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host or "http://localhost:3000",
        )
        return _langfuse_client
    except TypeError as e:
        if "ZodError" in str(e) or "Cannot set property" in str(e):
            _langfuse_initialization_error = (
                f"Langfuse initialization failed due to ZodError validation issue: {e}. "
                "This is a known compatibility issue. Langfuse observability will be disabled."
            )
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(_langfuse_initialization_error)
            return None
        raise
    except Exception as e:
        _langfuse_initialization_error = f"Langfuse initialization failed: {e}"
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Langfuse observability disabled due to initialization error: {e}")
        return None


def is_langfuse_enabled() -> bool:
    settings = get_settings()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return False
    client = get_langfuse_client()
    return client is not None


def get_langfuse_error() -> Optional[str]:
    return _langfuse_initialization_error
