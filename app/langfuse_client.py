"""Langfuse client initialization and utilities for observability.

This module handles Langfuse client initialization with workarounds for known issues:
- ZodError "Cannot set property message" issue (GitHub #7995)
- Provides dummy values for Langfuse-required fields that our project doesn't use
"""

import os
from typing import Optional

from langfuse import Langfuse

from app.config import settings

# Global Langfuse client instance
_langfuse_client: Optional[Langfuse] = None
_langfuse_initialization_error: Optional[str] = None


def _set_langfuse_dummy_env_vars() -> None:
    """Set dummy environment variables that Langfuse's ZodError validation expects.
    
    These are required by Langfuse's internal validation but our project doesn't
    actually use them. Setting them prevents ZodError from trying to modify read-only
    properties during validation.
    
    Reference: https://github.com/langfuse/langfuse/issues/7995
    """
    # Dummy values for Next.js/Node.js environment variables that Langfuse checks
    # These are only used by Langfuse's web UI (Next.js), not by the Python SDK
    # but the validation still runs and can cause ZodError issues
    
    # NEXT_PUBLIC_API_URL - Langfuse web UI expects this, but we don't use Next.js
    if "NEXT_PUBLIC_API_URL" not in os.environ:
        os.environ["NEXT_PUBLIC_API_URL"] = settings.langfuse_host or "http://localhost:3000"
    
    # NEXT_RUNTIME - Langfuse web UI expects this, but we're using Python not Node.js
    if "NEXT_RUNTIME" not in os.environ:
        os.environ["NEXT_RUNTIME"] = "nodejs"  # Dummy value, not actually used
    
    # NODE_ENV - Langfuse web UI expects this, but we're using Python
    if "NODE_ENV" not in os.environ:
        os.environ["NODE_ENV"] = "production"  # Dummy value, not actually used


def get_langfuse_client() -> Optional[Langfuse]:
    """Get or create the Langfuse client instance.
    
    Returns None if Langfuse is not configured (keys not set) or if initialization fails.
    This allows the application to run without Langfuse if not configured.
    
    Handles ZodError issues by setting dummy environment variables before initialization.
    """
    global _langfuse_client, _langfuse_initialization_error
    
    # Return None if Langfuse is not configured
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    
    # Return cached client if already initialized successfully
    if _langfuse_client is not None:
        return _langfuse_client
    
    # Return None if previous initialization failed
    if _langfuse_initialization_error is not None:
        return None
    
    try:
        # Set dummy environment variables to prevent ZodError validation issues
        # These satisfy Langfuse's internal validation without affecting our project
        _set_langfuse_dummy_env_vars()
        
        # Initialize client with error handling for ZodError issues
        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host or "http://localhost:3000",
        )
        
        return _langfuse_client
        
    except TypeError as e:
        # Catch ZodError-related TypeError: "Cannot set property message of ZodError"
        # This is a known issue with Langfuse's internal validation
        # Reference: https://github.com/langfuse/langfuse/issues/7995
        if "ZodError" in str(e) or "Cannot set property" in str(e):
            _langfuse_initialization_error = (
                f"Langfuse initialization failed due to ZodError validation issue: {e}. "
                "This is a known compatibility issue. Langfuse observability will be disabled."
            )
            # Log but don't crash - allow app to run without Langfuse
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(_langfuse_initialization_error)
            return None
        # Re-raise if it's a different TypeError
        raise
    except Exception as e:
        # Catch any other initialization errors
        _langfuse_initialization_error = f"Langfuse initialization failed: {e}"
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Langfuse observability disabled due to initialization error: {e}")
        return None


def is_langfuse_enabled() -> bool:
    """Check if Langfuse is configured and enabled.
    
    Returns True only if Langfuse is configured AND successfully initialized.
    """
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return False
    
    # Try to get client - this will initialize it if needed
    client = get_langfuse_client()
    return client is not None


def get_langfuse_error() -> Optional[str]:
    """Get the last Langfuse initialization error, if any.
    
    Useful for debugging why Langfuse might not be working.
    """
    return _langfuse_initialization_error

