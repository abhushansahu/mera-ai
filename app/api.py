import logging
import os
from typing import List, Dict, Optional, Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.config import settings
from app.db import Base, engine, get_db
from app.langfuse_client import get_langfuse_client, get_langfuse_error, is_langfuse_enabled
from app.orchestrator import UnifiedOrchestrator


class ChatRequest(BaseModel):
    user_id: str
    query: str
    model: str | None = None
    context_sources: Optional[List[Dict[str, str]]] = None


class ChatResponse(BaseModel):
    user_id: str
    answer: str


class StatusResponse(BaseModel):
    """Status endpoint response showing configuration and health."""

    status: str
    required_api_keys: Dict[str, str]
    database_connected: bool
    database_error: Optional[str] = None
    optional_services: Dict[str, bool]


def create_app() -> FastAPI:
    """Create a FastAPI application instance.

    Validates all required API keys and database connection at startup.
    Fails fast if any required configuration is missing.
    """
    app = FastAPI(
        title="Unified AI Assistant",
        description="A unified AI assistant with persistent memory, context management, and multi-agent orchestration.",
    )
    # Initialize Langfuse with error handling for ZodError issues
    if is_langfuse_enabled():
        langfuse_client = get_langfuse_client()
        if langfuse_client:
            logger.info("Langfuse observability enabled")
        else:
            error_msg = get_langfuse_error()
            if error_msg:
                logger.warning(f"Langfuse keys configured but client initialization failed: {error_msg}")
            else:
                logger.warning("Langfuse keys configured but client initialization failed (unknown error)")
    else:
        logger.info("Langfuse observability disabled (keys not configured)")
    
    orchestrator = UnifiedOrchestrator()
    database_connected = False
    database_error = None

    @app.on_event("startup")
    async def startup_event() -> None:
        """Validate database connection on startup."""
        nonlocal database_connected, database_error
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
            database_connected = True
            database_error = None
        except OperationalError as e:
            database_connected = False
            database_error = str(e)
            logger.error(f"Database connection failed: {database_error}")
        except Exception as e:  # noqa: BLE001
            database_connected = False
            database_error = str(e)
            logger.error(f"Database initialization failed: {database_error}")

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        """Cleanup on shutdown."""
        from app.llm_client import close_async_client
        await close_async_client()
        if hasattr(orchestrator, "obsidian"):
            await orchestrator.obsidian.close()

    @app.get("/status", response_model=StatusResponse)
    async def status() -> StatusResponse:
        """Get server status and configuration information."""
        db_display = "configured"
        if settings.database_url and "@" in settings.database_url:
            db_display = settings.database_url.split("@")[-1]
        
        # Mem0 status: show host if self-hosted, or API key status if external
        mem0_status = "✓ Configured"
        if settings.mem0_host:
            mem0_status = f"✓ Self-hosted ({settings.mem0_host})"
        elif settings.mem0_api_key:
            mem0_status = "✓ External (API key set)"
        else:
            mem0_status = "✗ Not configured"
        
        return StatusResponse(
            status="operational",
            required_api_keys={
                "OPENROUTER_API_KEY": "✓ Set" if settings.openrouter_api_key else "✗ Missing",
                "MEM0": mem0_status,
                "DATABASE_URL": f"✓ Set ({db_display})" if settings.database_url else "✗ Missing",
            },
            database_connected=database_connected,
            database_error=database_error,
            optional_services={
                "LANGFUSE": is_langfuse_enabled(),  # True only if configured AND successfully initialized
                "OBSIDIAN": bool(settings.obsidian_rest_token),
            },
        )

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
        """Process a chat query through the unified orchestrator."""
        if not database_connected:
            raise HTTPException(
                status_code=503,
                detail="Database is not connected. Please check your DATABASE_URL configuration."
            )
        answer = await orchestrator.process_query(
            user_id=request.user_id,
            query=request.query,
            preferred_model=request.model,
            db=db,
            context_sources=request.context_sources,
        )
        return ChatResponse(user_id=request.user_id, answer=answer)

    # Mem0 proxy endpoints for Obsidian plugin integration
    class AddMemoryRequest(BaseModel):
        user_id: str
        messages: str | list[dict[str, str]]
        metadata: Optional[dict] = None

    class SearchMemoryRequest(BaseModel):
        user_id: str
        query: str
        limit: int = 5

    @app.post("/mem0/add")
    async def add_memory(request: AddMemoryRequest) -> Dict[str, str]:
        """Add a memory via Mem0 (proxy endpoint for Obsidian plugin)."""
        from app.memory_mem0 import Mem0Wrapper
        try:
            mem0 = Mem0Wrapper()
            await mem0.store(
                user_id=request.user_id,
                text=request.messages if isinstance(request.messages, str) else str(request.messages),
                metadata=request.metadata,
            )
            return {"status": "success", "message": "Memory added"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/mem0/search")
    async def search_memories(request: SearchMemoryRequest) -> Dict[str, Any]:
        """Search memories via Mem0 (proxy endpoint for Obsidian plugin)."""
        from app.memory_mem0 import Mem0Wrapper
        try:
            mem0 = Mem0Wrapper()
            results = await mem0.search(
                user_id=request.user_id,
                query=request.query,
                limit=request.limit,
            )
            return {"status": "success", "results": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/mem0/get_all/{user_id}")
    async def get_all_memories(user_id: str, limit: int = 100) -> Dict[str, Any]:
        """Get all memories for a user via Mem0 (proxy endpoint for Obsidian plugin)."""
        from app.memory_mem0 import Mem0Wrapper
        try:
            mem0 = Mem0Wrapper()
            # Note: Mem0Wrapper doesn't have get_all, so we'll use search with a broad query
            results = await mem0.search(
                user_id=user_id,
                query="",
                limit=limit,
            )
            return {"status": "success", "results": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


app = create_app()


