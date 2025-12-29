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

from app.core import ContextSource
from app.db import Base, engine, get_db
from app.infrastructure.config.settings import get_settings
from app.infrastructure.observability import (
    get_langsmith_client,
    get_langsmith_error,
    is_langsmith_enabled,
)
from app.orchestrators import LangChainUnifiedOrchestrator
from app.adapters.openrouter import _close_async_client
from app.spaces.space_manager import SpaceManager
from app.spaces.space_model import SpaceConfig, SpaceStatus, SpaceUsage
# Import models to ensure they're registered with SQLAlchemy Base
from app.models import SpaceRecord, SpaceUsageRecord  # noqa: F401

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    user_id: str
    query: str
    model: str | None = None
    context_sources: Optional[List[Dict[str, str]]] = None
    space_id: Optional[str] = None


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


class CreateSpaceRequest(BaseModel):
    space_id: str
    name: str
    owner_id: str
    monthly_token_budget: int = 1_000_000
    monthly_api_calls: int = 10_000
    preferred_model: str = "openai/gpt-4o-mini"


class SpaceResponse(BaseModel):
    space_id: str
    name: str
    owner_id: str
    status: str
    monthly_token_budget: int
    monthly_api_calls: int
    preferred_model: str


class SpaceUsageResponse(BaseModel):
    space_id: str
    month: str
    tokens_used: int
    api_calls_used: int
    cost_usd: float
    tokens_remaining: int


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
        
        # Initialize space manager if space_id provided
        space_manager = None
        if request.space_id:
            space_manager = SpaceManager(db)
            try:
                await space_manager.switch_space(request.space_id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
        
        result = await orchestrator.process_query(
            user_id=request.user_id,
            query=request.query,
            model=request.model,
            context_sources=context_sources,
            db=db,
            space_manager=space_manager,
        )
        return ChatResponse(user_id=request.user_id, answer=result.answer)

    @app.post("/mem0/add")
    async def add_memory(request: AddMemoryRequest) -> Dict[str, str]:
        from app.adapters.chroma import ChromaMemoryAdapter
        from app.infrastructure.config.settings import get_settings
        try:
            settings = get_settings()
            memory = ChromaMemoryAdapter(
                host=settings.chroma_host,
                port=settings.chroma_port,
                collection_name=settings.chroma_collection_name,
                persist_directory=settings.chroma_persist_dir,
            )
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
        from app.adapters.chroma import ChromaMemoryAdapter
        from app.infrastructure.config.settings import get_settings
        try:
            settings = get_settings()
            memory = ChromaMemoryAdapter(
                host=settings.chroma_host,
                port=settings.chroma_port,
                collection_name=settings.chroma_collection_name,
                persist_directory=settings.chroma_persist_dir,
            )
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
        from app.adapters.chroma import ChromaMemoryAdapter
        from app.infrastructure.config.settings import get_settings
        try:
            settings = get_settings()
            memory = ChromaMemoryAdapter(
                host=settings.chroma_host,
                port=settings.chroma_port,
                collection_name=settings.chroma_collection_name,
                persist_directory=settings.chroma_persist_dir,
            )
            memories = await memory.search(
                user_id=user_id,
                query="",
                limit=limit,
            )
            results = [{"text": m.text, "metadata": m.metadata, "score": m.score} for m in memories]
            return {"status": "success", "results": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Space management endpoints
    @app.post("/spaces/create", response_model=SpaceResponse)
    async def create_space(
        request: CreateSpaceRequest,
        db: AsyncSession = Depends(get_db),
    ) -> SpaceResponse:
        """Create a new space."""
        if not database_connected:
            raise HTTPException(
                status_code=503,
                detail="Database is not connected. Please check your DATABASE_URL configuration."
            )
        
        space_manager = SpaceManager(db)
        config = SpaceConfig(
            space_id=request.space_id,
            name=request.name,
            owner_id=request.owner_id,
            monthly_token_budget=request.monthly_token_budget,
            monthly_api_calls=request.monthly_api_calls,
            preferred_model=request.preferred_model,
        )
        
        try:
            created_config = await space_manager.create_space(config)
            return SpaceResponse(
                space_id=created_config.space_id,
                name=created_config.name,
                owner_id=created_config.owner_id,
                status=created_config.status.value,
                monthly_token_budget=created_config.monthly_token_budget,
                monthly_api_calls=created_config.monthly_api_calls,
                preferred_model=created_config.preferred_model,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error creating space: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/spaces/list", response_model=List[SpaceResponse])
    async def list_spaces(
        owner_id: str,
        db: AsyncSession = Depends(get_db),
    ) -> List[SpaceResponse]:
        """List all spaces for an owner."""
        if not database_connected:
            raise HTTPException(
                status_code=503,
                detail="Database is not connected. Please check your DATABASE_URL configuration."
            )
        
        space_manager = SpaceManager(db)
        try:
            spaces = await space_manager.list_spaces(owner_id)
            return [
                SpaceResponse(
                    space_id=space.space_id,
                    name=space.name,
                    owner_id=space.owner_id,
                    status=space.status.value,
                    monthly_token_budget=space.monthly_token_budget,
                    monthly_api_calls=space.monthly_api_calls,
                    preferred_model=space.preferred_model,
                )
                for space in spaces
            ]
        except Exception as e:
            logger.error(f"Error listing spaces: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/spaces/switch", response_model=SpaceResponse)
    async def switch_space(
        space_id: str,
        db: AsyncSession = Depends(get_db),
    ) -> SpaceResponse:
        """Switch to a different space."""
        if not database_connected:
            raise HTTPException(
                status_code=503,
                detail="Database is not connected. Please check your DATABASE_URL configuration."
            )
        
        space_manager = SpaceManager(db)
        try:
            config = await space_manager.switch_space(space_id)
            return SpaceResponse(
                space_id=config.space_id,
                name=config.name,
                owner_id=config.owner_id,
                status=config.status.value,
                monthly_token_budget=config.monthly_token_budget,
                monthly_api_calls=config.monthly_api_calls,
                preferred_model=config.preferred_model,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error switching space: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/spaces/current", response_model=SpaceResponse)
    async def get_current_space(
        db: AsyncSession = Depends(get_db),
    ) -> SpaceResponse:
        """Get current space."""
        if not database_connected:
            raise HTTPException(
                status_code=503,
                detail="Database is not connected. Please check your DATABASE_URL configuration."
            )
        
        space_manager = SpaceManager(db)
        try:
            config = space_manager.get_current_space()
            return SpaceResponse(
                space_id=config.space_id,
                name=config.name,
                owner_id=config.owner_id,
                status=config.status.value,
                monthly_token_budget=config.monthly_token_budget,
                monthly_api_calls=config.monthly_api_calls,
                preferred_model=config.preferred_model,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error getting current space: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/spaces/{space_id}/usage", response_model=SpaceUsageResponse)
    async def get_space_usage(
        space_id: str,
        month: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
    ) -> SpaceUsageResponse:
        """Get space usage for a specific month."""
        if not database_connected:
            raise HTTPException(
                status_code=503,
                detail="Database is not connected. Please check your DATABASE_URL configuration."
            )
        
        space_manager = SpaceManager(db)
        try:
            usage = await space_manager.get_space_usage(space_id, month)
            # Get space config to calculate remaining
            await space_manager.switch_space(space_id)
            config = space_manager.get_current_space()
            remaining = usage.get_budget_remaining(config)
            
            return SpaceUsageResponse(
                space_id=usage.space_id,
                month=usage.month,
                tokens_used=usage.tokens_used,
                api_calls_used=usage.api_calls_used,
                cost_usd=usage.cost_usd,
                tokens_remaining=remaining,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error getting space usage: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/spaces/{space_id}")
    async def delete_space(
        space_id: str,
        permanently: bool = False,
        db: AsyncSession = Depends(get_db),
    ) -> Dict[str, str]:
        """Delete or archive a space."""
        if not database_connected:
            raise HTTPException(
                status_code=503,
                detail="Database is not connected. Please check your DATABASE_URL configuration."
            )
        
        space_manager = SpaceManager(db)
        try:
            await space_manager.delete_space(space_id, permanently=permanently)
            return {
                "status": "success",
                "message": f"Space {'deleted' if permanently else 'archived'}: {space_id}",
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error deleting space: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    return app


app = create_app()
