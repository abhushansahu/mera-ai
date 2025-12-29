import logging
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.types import ContextSource
from app.db import Base, engine, get_db
from app.infrastructure.config.settings import get_settings
from app.infrastructure.observability import (
    get_langsmith_client,
    get_langsmith_error,
    is_langsmith_enabled,
)
from app.orchestrators import LangChainUnifiedOrchestrator
from app.adapters.openrouter.llm import _close_async_client

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    user_id: str
    query: str
    model: str | None = None
    context_sources: Optional[List[Dict[str, str]]] = None


class ChatResponse(BaseModel):
    user_id: str
    answer: str


class StatusResponse(BaseModel):
    status: str
    required_api_keys: Dict[str, str]
    database_connected: bool
    database_error: Optional[str] = None
    optional_services: Dict[str, bool]


class AddMemoryRequest(BaseModel):
    user_id: str
    messages: str | list[dict[str, str]]
    metadata: Optional[dict] = None


class SearchMemoryRequest(BaseModel):
    user_id: str
    query: str
    limit: int = 5


def create_app() -> FastAPI:
    app = FastAPI(
        title="Unified AI Assistant",
        description="A unified AI assistant with persistent memory, context management, and multi-agent orchestration.",
    )
    
    # Add CORS middleware to handle OPTIONS requests
    settings = get_settings()
    # Allow CORS origins from environment or default to all for development
    if settings.cors_origins:
        # Parse comma-separated origins
        allow_origins = [origin.strip() for origin in settings.cors_origins.split(",")]
        allow_credentials = True
    else:
        # Default to all origins for development (change in production)
        # Note: Cannot use ["*"] with allow_credentials=True, so we disable credentials
        allow_origins = ["*"]
        allow_credentials = False
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],  # Allows all methods including OPTIONS
        allow_headers=["*"],
    )
    
    # Add exception handler for validation errors to provide better error messages
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle validation errors and return detailed error messages."""
        errors = exc.errors()
        error_details = []
        
        # Check if the issue is missing Content-Type header
        content_type = request.headers.get("content-type", "")
        missing_content_type = not content_type or "application/json" not in content_type
        
        for error in errors:
            field_path = ".".join(str(loc) for loc in error["loc"])
            error_msg = error["msg"]
            
            # Provide helpful message for missing Content-Type
            if missing_content_type and error["type"] == "model_attributes_type":
                error_msg = (
                    f"{error_msg}. "
                    "Make sure to include 'Content-Type: application/json' header in your request."
                )
            
            error_details.append({
                "field": field_path,
                "message": error_msg,
                "type": error["type"]
            })
        
        response_content = {
            "detail": "Validation error",
            "errors": error_details,
        }
        
        # Add helpful hint about Content-Type if missing
        if missing_content_type:
            response_content["hint"] = (
                "Your request is missing the 'Content-Type: application/json' header. "
                "Add this header to your request to send JSON data."
            )
        
        return JSONResponse(
            status_code=422,
            content=response_content,
        )
    
    if is_langsmith_enabled():
        langsmith_client = get_langsmith_client()
        if langsmith_client:
            logger.info("LangSmith observability enabled")
        else:
            error_msg = get_langsmith_error()
            if error_msg:
                logger.warning(f"LangSmith keys configured but client initialization failed: {error_msg}")
            else:
                logger.warning("LangSmith keys configured but client initialization failed (unknown error)")
    else:
        logger.info("LangSmith observability disabled (keys not configured)")
    
    logger.info("Using LangChain unified orchestrator")
    orchestrator = LangChainUnifiedOrchestrator()
    
    database_connected = False
    database_error = None

    @app.on_event("startup")
    async def startup_event() -> None:
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
        except Exception as e:
            database_connected = False
            database_error = str(e)
            logger.error(f"Database initialization failed: {database_error}")

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        await _close_async_client()

    @app.get("/status", response_model=StatusResponse)
    async def status() -> StatusResponse:
        current_settings = get_settings()
        db_display = "configured"
        if current_settings.database_url and "@" in current_settings.database_url:
            db_display = current_settings.database_url.split("@")[-1]
        
        chroma_status = "✓ Configured" if current_settings.chroma_host or True else "✗ Not configured"
        
        return StatusResponse(
            status="operational",
            required_api_keys={
                "OPENROUTER_API_KEY": "✓ Set" if current_settings.openrouter_api_key else "✗ Missing",
                "CHROMA": chroma_status,
                "DATABASE_URL": f"✓ Set ({db_display})" if current_settings.database_url else "✗ Missing",
            },
            database_connected=database_connected,
            database_error=database_error,
            optional_services={
                "LANGSMITH": is_langsmith_enabled(),
                "OBSIDIAN": bool(current_settings.obsidian_rest_token),
            },
        )

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
        if not database_connected:
            raise HTTPException(
                status_code=503,
                detail="Database is not connected. Please check your DATABASE_URL configuration."
            )
        
        context_sources = None
        if request.context_sources:
            context_sources = [ContextSource(**cs) for cs in request.context_sources]
        
        result = await orchestrator.process_query(
            user_id=request.user_id,
            query=request.query,
            model=request.model,
            context_sources=context_sources,
            db=db,
        )
        return ChatResponse(user_id=request.user_id, answer=result.answer)

    @app.post("/mem0/add")
    async def add_memory(request: AddMemoryRequest) -> Dict[str, str]:
        from app.memory_factory import get_memory_manager
        try:
            memory = get_memory_manager()
            await memory.store(
                user_id=request.user_id,
                text=request.messages if isinstance(request.messages, str) else str(request.messages),
                metadata=request.metadata,
            )
            return {"status": "success", "message": "Memory added"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/mem0/search")
    async def search_memories(request: SearchMemoryRequest) -> Dict[str, Any]:
        from app.memory_factory import get_memory_manager
        try:
            memory = get_memory_manager()
            memories = await memory.search(
                user_id=request.user_id,
                query=request.query,
                limit=request.limit,
            )
            results = [{"text": m.text, "metadata": m.metadata, "score": m.score} for m in memories]
            return {"status": "success", "results": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/mem0/get_all/{user_id}")
    async def get_all_memories(user_id: str, limit: int = 100) -> Dict[str, Any]:
        from app.memory_factory import get_memory_manager
        try:
            memory = get_memory_manager()
            memories = await memory.search(
                user_id=user_id,
                query="",
                limit=limit,
            )
            results = [{"text": m.text, "metadata": m.metadata, "score": m.score} for m in memories]
            return {"status": "success", "results": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


app = create_app()
