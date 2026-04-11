import json
import logging
import time
from threading import Lock
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.core import ContextSource
from app.contracts import (
    CONTRACT_VERSION,
    ChatRequestContract,
    ChatResponseContract,
    ContextSourceContract,
    FeatureFlagsContract,
    ObsidianContextEventContract,
    StatusResponseContract,
)
from app.db import Base, engine, get_db
from app.config import get_settings
from app.observability import is_langsmith_enabled
from app.performance import TimingCollector, log_timing_summary, set_request_id
from app.orchestrator import CrewAIOrchestrator
from app.adapters.openrouter import _close_async_client
from app.adapters.chroma import close_embedding_client
from app.adapters.obsidian import ObsidianClient
from app.auth import AuthPrincipal, get_optional_principal
from app.multi_agent_context_system import close_production_resources
from app.spaces import SpaceConfig, SpaceManager, SpaceStatus, SpaceUsage
# Import models to ensure they're registered with SQLAlchemy Base
from app.models import ConversationMessage, ConversationThread, ProviderCredential, SpaceRecord, SpaceUsageRecord  # noqa: F401
from app.services.credential_service import upsert_provider_key

logger = logging.getLogger(__name__)

_OBSIDIAN_CONTEXT_LOCK = Lock()
_OBSIDIAN_CONTEXT_SESSIONS: Dict[str, Dict[str, Any]] = {}


class ChatRequest(ChatRequestContract):
    pass


class ChatResponse(ChatResponseContract):
    pass


class StatusResponse(StatusResponseContract):
    pass


class AddMemoryRequest(BaseModel):
    user_id: Optional[str] = None
    messages: str | list[dict[str, str]]
    metadata: Optional[dict] = None
    space_id: Optional[str] = None


class SearchMemoryRequest(BaseModel):
    user_id: Optional[str] = None
    query: str
    limit: int = 5
    space_id: Optional[str] = None


class BoundaryContextResearchRequest(BaseModel):
    query: str
    context_sources: List[ContextSourceContract]


class BoundaryMemoryStoreRequest(BaseModel):
    user_id: Optional[str] = None
    text: str
    metadata: Optional[dict] = None
    space_id: Optional[str] = None


class BoundaryMemorySearchRequest(BaseModel):
    user_id: Optional[str] = None
    query: str
    limit: int = 5
    space_id: Optional[str] = None


class WikiLintRequest(BaseModel):
    save_report: bool = True


class WikiLintResponse(BaseModel):
    space_id: str
    total_notes: int
    summary: Dict[str, int]
    issues: Dict[str, List[str]]


class CreateSpaceRequest(BaseModel):
    space_id: str
    name: str
    owner_id: Optional[str] = None
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


class ThreadCreateRequest(BaseModel):
    user_id: Optional[str] = None
    space_id: Optional[str] = None
    title: Optional[str] = None


class ThreadRenameRequest(BaseModel):
    user_id: Optional[str] = None
    title: str


class ThreadResponse(BaseModel):
    id: str
    user_id: str
    space_id: Optional[str] = None
    title: str
    archived: bool
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    id: str
    user_id: str
    thread_id: str
    role: str
    content: str
    created_at: str
    metadata: Dict[str, Any]


class ProviderKeyUpsertRequest(BaseModel):
    owner_id: Optional[str] = None
    provider: str
    api_key: str


class ProviderKeyResponse(BaseModel):
    owner_id: str
    provider: str
    key_version: str
    last4: str
    is_active: bool
    updated_at: str


class ObsidianLinkRequest(BaseModel):
    user_id: Optional[str] = None
    thread_id: str
    note_path: str
    summary: Optional[str] = None


class ObsidianIndexRequest(BaseModel):
    prefixes: List[str] = Field(default_factory=lambda: ["Wiki"])


class ObsidianContextEventRequest(ObsidianContextEventContract):
    pass


class ObsidianContextIngestRequest(BaseModel):
    user_id: Optional[str] = None
    space_id: Optional[str] = None
    session_id: Optional[str] = None
    event: ObsidianContextEventRequest


class ObsidianContextHeartbeatRequest(BaseModel):
    user_id: Optional[str] = None
    space_id: Optional[str] = None
    session_id: Optional[str] = None
    active_note_path: Optional[str] = None
    active_note_title: Optional[str] = None


class ObsidianContextSessionResponse(BaseModel):
    session_id: str
    user_id: str
    space_id: Optional[str] = None
    active_note_path: Optional[str] = None
    active_note_title: Optional[str] = None
    active_selection: Optional[str] = None
    recent_events: List[Dict[str, Any]] = Field(default_factory=list)
    last_event_at: Optional[str] = None
    plugin_connected: bool = False
    last_heartbeat_at: Optional[str] = None
    last_heartbeat_age_ms: Optional[int] = None


class FeatureFlagsResponse(FeatureFlagsContract):
    pass


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
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
    
    if is_langsmith_enabled():
        logger.info("LangSmith observability enabled")
    else:
        logger.info("LangSmith observability disabled (keys not configured)")
    
    logger.info("Using CrewAI unified orchestrator")
    orchestrator = CrewAIOrchestrator()
    app.state.orchestrator = orchestrator
    
    database_connected = False
    database_error = None

    @app.on_event("startup")
    async def startup_event() -> None:
        nonlocal database_connected, database_error
        try:
            startup_settings = get_settings()
            if (
                startup_settings.secure_settings_enabled
                and startup_settings.secret_encryption_key == "dev-only-change-me"
                and not startup_settings.allow_insecure_secret_key
            ):
                raise RuntimeError("SECRET_ENCRYPTION_KEY must be set when secure settings are enabled.")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.execute(text("SELECT 1"))
                await conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS conversation_threads (
                            id VARCHAR PRIMARY KEY,
                            user_id VARCHAR NOT NULL,
                            space_id VARCHAR NULL,
                            title VARCHAR NOT NULL,
                            archived BOOLEAN NOT NULL DEFAULT FALSE,
                            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                )
                await conn.execute(text("ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS thread_id VARCHAR"))
                await conn.execute(text("ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb"))
                await conn.execute(
                    text(
                        """
                        UPDATE conversation_messages
                        SET thread_id = COALESCE(thread_id, CONCAT('legacy-', user_id))
                        WHERE thread_id IS NULL
                        """
                    )
                )
                await conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS provider_credentials (
                            id SERIAL PRIMARY KEY,
                            owner_id VARCHAR NOT NULL,
                            provider VARCHAR NOT NULL,
                            encrypted_value TEXT NOT NULL,
                            key_version VARCHAR NOT NULL DEFAULT 'v1',
                            last4 VARCHAR(4) NOT NULL,
                            is_active BOOLEAN NOT NULL DEFAULT TRUE,
                            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                            UNIQUE(owner_id, provider)
                        )
                        """
                    )
                )
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

    @app.middleware("http")
    async def add_request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid4())
        set_request_id(request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        response.headers["x-response-time-ms"] = f"{(time.perf_counter() - started) * 1000:.2f}"
        response.headers["x-contract-version"] = CONTRACT_VERSION
        return response

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        await _close_async_client()
        await close_embedding_client()
        await close_production_resources()

    @app.get("/status", response_model=StatusResponse)
    async def status() -> StatusResponse:
        current_settings = get_settings()
        chroma_status = "✓ Configured" if current_settings.chroma_host or True else "✗ Not configured"
        
        return StatusResponse(
            status="operational",
            required_api_keys={
                "OPENROUTER_API_KEY": "✓ Set" if current_settings.openrouter_api_key else "Optional (missing)",
                "LMSTUDIO_BASE_URL": current_settings.lmstudio_base_url,
                "CURSOR_AGENT_BASE_URL": current_settings.cursor_agent_base_url,
                "CHROMA": chroma_status,
                "DATABASE_URL": "✓ Set" if current_settings.database_url else "✗ Missing",
            },
            database_connected=database_connected,
            database_error=database_error,
            optional_services={
                "LANGSMITH": is_langsmith_enabled(),
                "OBSIDIAN": bool(current_settings.obsidian_rest_token),
            },
        )

    @app.get("/contracts/version")
    async def contract_version() -> Dict[str, str]:
        return {"contract_version": CONTRACT_VERSION}

    @app.get("/features", response_model=FeatureFlagsResponse)
    async def get_feature_flags() -> FeatureFlagsResponse:
        settings = get_settings()
        return FeatureFlagsResponse(
            threading=settings.threading_enabled,
            per_message_model=settings.per_message_model_enabled,
            secure_provider_settings=settings.secure_settings_enabled,
            obsidian_advanced=settings.obsidian_advanced_enabled,
            rpi_compact_layout=settings.rpi_compact_layout_enabled,
            obsidian_event_sync=settings.obsidian_event_sync_enabled,
        )

    def _effective_user_id(principal: AuthPrincipal, provided_user_id: Optional[str]) -> str:
        if provided_user_id and provided_user_id != principal.user_id and not principal.is_service:
            raise HTTPException(status_code=403, detail="User identity mismatch.")
        return principal.user_id if not principal.is_service else (provided_user_id or principal.user_id)

    def _assert_provider_owner(principal: AuthPrincipal, owner_id: Optional[str]) -> str:
        if owner_id and owner_id != principal.user_id and not principal.is_service:
            raise HTTPException(status_code=403, detail="Owner identity mismatch.")
        return principal.user_id if not principal.is_service else (owner_id or principal.user_id)

    def _parse_context_sources_or_422(
        raw_sources: Optional[List[ContextSourceContract | Dict[str, Any]]]
    ) -> Optional[List[ContextSource]]:
        if not raw_sources:
            return None
        allowed_types = {"FILE", "DIRECTORY", "URL", "API", "DATABASE", "MEMORY", "OBSIDIAN"}
        parsed: List[ContextSource] = []
        for source in raw_sources:
            source_payload = source.model_dump() if hasattr(source, "model_dump") else source
            source_type = str(source_payload.get("type", "")).upper()
            if source_type not in allowed_types:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported context source type: {source_payload.get('type')}",
                )
            parsed.append(ContextSource(**{**source_payload, "type": source_type}))
        return parsed

    def _obsidian_session_key(user_id: str, space_id: Optional[str], session_id: Optional[str]) -> str:
        return f"{user_id}:{space_id or 'global'}:{session_id or 'default'}"

    def _sse_event(payload: Dict[str, Any]) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def _assert_obsidian_plugin_auth(req: Request) -> None:
        settings = get_settings()
        required = (settings.obsidian_plugin_shared_secret or "").strip()
        if not required:
            return
        provided = req.headers.get("x-obsidian-plugin-secret", "").strip()
        if not provided or provided != required:
            raise HTTPException(status_code=401, detail="Invalid Obsidian plugin secret.")

    async def _ensure_thread(
        db: AsyncSession,
        *,
        user_id: str,
        space_id: Optional[str],
        thread_id: Optional[str],
        title_hint: Optional[str] = None,
    ) -> ConversationThread:
        if thread_id:
            if thread_id.startswith("legacy-"):
                legacy_thread = await db.scalar(
                    select(ConversationThread).where(
                        ConversationThread.id == thread_id,
                        ConversationThread.user_id == user_id,
                    )
                )
                if legacy_thread is None:
                    legacy_thread = ConversationThread(
                        id=thread_id,
                        user_id=user_id,
                        space_id=space_id,
                        title="Legacy Thread",
                        archived=False,
                    )
                    db.add(legacy_thread)
                    await db.commit()
                    await db.refresh(legacy_thread)
                return legacy_thread
            existing = await db.scalar(
                select(ConversationThread).where(
                    ConversationThread.id == thread_id,
                    ConversationThread.user_id == user_id,
                    ConversationThread.archived.is_(False),
                )
            )
            if existing is None:
                raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")
            return existing

        default_title = (title_hint or "New Thread").strip()
        if len(default_title) > 80:
            default_title = default_title[:77] + "..."
        thread = ConversationThread(
            id=str(uuid4()),
            user_id=user_id,
            space_id=space_id,
            title=default_title or "New Thread",
            archived=False,
        )
        db.add(thread)
        await db.commit()
        await db.refresh(thread)
        return thread

    @app.post("/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> ChatResponse:
        timer = TimingCollector()
        effective_user_id = _effective_user_id(principal, request.user_id)
        if not database_connected:
            raise HTTPException(
                status_code=503,
                detail="Database is not connected. Please check your DATABASE_URL configuration."
            )
        
        context_sources = None
        if request.context_sources:
            with timer.measure("parse_context_sources"):
                context_sources = _parse_context_sources_or_422(request.context_sources)
        
        # Initialize space manager if space_id provided
        space_manager = None
        if request.space_id:
            with timer.measure("switch_space"):
                space_manager = SpaceManager(db)
                try:
                    await space_manager.switch_space(request.space_id)
                except ValueError as e:
                    raise HTTPException(status_code=404, detail=str(e))
        
        with timer.measure("process_query"):
            thread = await _ensure_thread(
                db,
                user_id=effective_user_id,
                space_id=request.space_id,
                thread_id=request.thread_id,
                title_hint=request.query,
            )
            result = await app.state.orchestrator.process_query(
                user_id=effective_user_id,
                query=request.query,
                model=request.model,
                provider=request.provider,
                context_sources=context_sources,
                db=db,
                space_manager=space_manager,
                thread_id=thread.id,
            )
        log_timing_summary(logger, "chat_completed", timer.timings_ms)
        metadata = {
            **result.metadata,
            "api_timings_ms": timer.timings_ms,
            "contract_version": CONTRACT_VERSION,
            "obsidian_context_attached": any(
                (src.type or "").upper() == "OBSIDIAN" for src in (context_sources or [])
            ),
        }
        return ChatResponse(
            user_id=effective_user_id,
            answer=result.answer,
            research=result.research,
            plan=result.plan,
            metadata={**metadata, "thread_id": thread.id},
        )

    async def _memory_adapter_for_optional_space(
        space_id: Optional[str],
        db: AsyncSession,
    ):
        from app.adapters.chroma import ChromaMemoryAdapter
        from app.config import get_settings

        settings = get_settings()
        collection_name = settings.chroma_collection_name
        if space_id:
            space_manager = SpaceManager(db)
            await space_manager.switch_space(space_id)
            config = space_manager.get_current_space()
            collection_name = config.mem0_collection_name
        return ChromaMemoryAdapter(
            host=settings.chroma_host,
            port=settings.chroma_port,
            collection_name=collection_name,
            persist_directory=settings.chroma_persist_dir,
        )

    @app.post("/mem0/add")
    async def add_memory(
        request: AddMemoryRequest,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, str]:
        try:
            effective_user_id = _effective_user_id(principal, request.user_id)
            memory = await _memory_adapter_for_optional_space(request.space_id, db)
            await memory.store(
                user_id=effective_user_id,
                text=request.messages if isinstance(request.messages, str) else str(request.messages),
                metadata=request.metadata,
            )
            return {"status": "success", "message": "Memory added"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/mem0/search")
    async def search_memories(
        request: SearchMemoryRequest,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, Any]:
        try:
            effective_user_id = _effective_user_id(principal, request.user_id)
            memory = await _memory_adapter_for_optional_space(request.space_id, db)
            memories = await memory.search(
                user_id=effective_user_id,
                query=request.query,
                limit=request.limit,
            )
            results = [{"text": m.text, "metadata": m.metadata, "score": m.score} for m in memories]
            return {"status": "success", "results": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/internal/boundary/context/research")
    async def boundary_context_research(
        request: BoundaryContextResearchRequest,
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, str]:
        try:
            _ = principal
            sources = _parse_context_sources_or_422(request.context_sources) or []
            content = await app.state.orchestrator.context_boundary.research(
                query=request.query,
                context_sources=sources,
            )
            return {"content": content, "contract_version": CONTRACT_VERSION}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/internal/boundary/memory/store")
    async def boundary_memory_store(
        request: BoundaryMemoryStoreRequest,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, str]:
        try:
            effective_user_id = _effective_user_id(principal, request.user_id)
            if request.space_id is None:
                await app.state.orchestrator.memory_boundary.store(
                    user_id=effective_user_id,
                    text=request.text,
                    metadata=request.metadata,
                )
            else:
                memory = await _memory_adapter_for_optional_space(request.space_id, db)
                await memory.store(
                    user_id=effective_user_id,
                    text=request.text,
                    metadata=request.metadata,
                )
            return {"status": "ok", "contract_version": CONTRACT_VERSION}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/internal/boundary/memory/search")
    async def boundary_memory_search(
        request: BoundaryMemorySearchRequest,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, Any]:
        try:
            effective_user_id = _effective_user_id(principal, request.user_id)
            if request.space_id is None:
                results = await app.state.orchestrator.memory_boundary.search(
                    user_id=effective_user_id,
                    query=request.query,
                    limit=request.limit,
                )
            else:
                memory = await _memory_adapter_for_optional_space(request.space_id, db)
                raw = await memory.search(
                    user_id=effective_user_id,
                    query=request.query,
                    limit=request.limit,
                )
                results = [{"text": m.text, "metadata": m.metadata, "score": m.score} for m in raw]
                return {"results": results, "contract_version": CONTRACT_VERSION}
            return {
                "results": [
                    {"text": m.text, "metadata": m.metadata, "score": m.score}
                    for m in results
                ],
                "contract_version": CONTRACT_VERSION,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/mem0/get_all/{user_id}")
    async def get_all_memories(
        user_id: str,
        limit: int = 100,
        space_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, Any]:
        try:
            effective_user_id = _effective_user_id(principal, user_id)
            memory = await _memory_adapter_for_optional_space(space_id, db)
            memories = await memory.search(
                user_id=effective_user_id,
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
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> SpaceResponse:
        """Create a new space."""
        if not database_connected:
            raise HTTPException(
                status_code=503,
                detail="Database is not connected. Please check your DATABASE_URL configuration."
            )
        
        space_manager = SpaceManager(db)
        owner_id = _assert_provider_owner(principal, request.owner_id)
        config = SpaceConfig(
            space_id=request.space_id,
            name=request.name,
            owner_id=owner_id,
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
        owner_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> List[SpaceResponse]:
        """List all spaces for an owner."""
        if not database_connected:
            raise HTTPException(
                status_code=503,
                detail="Database is not connected. Please check your DATABASE_URL configuration."
            )
        
        space_manager = SpaceManager(db)
        try:
            effective_owner_id = _assert_provider_owner(principal, owner_id)
            spaces = await space_manager.list_spaces(effective_owner_id)
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

    @app.get("/spaces/{space_id}", response_model=SpaceResponse)
    async def get_space(
        space_id: str,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> SpaceResponse:
        result = await db.execute(select(SpaceRecord).where(SpaceRecord.space_id == space_id))
        record = result.scalar_one_or_none()
        if record is None:
            raise HTTPException(status_code=404, detail="Space not found.")
        if record.owner_id != principal.user_id and not principal.is_service:
            raise HTTPException(status_code=403, detail="Not authorized for this space.")
        config = record.config or {}
        return SpaceResponse(
            space_id=record.space_id,
            name=record.name,
            owner_id=record.owner_id,
            status=record.status,
            monthly_token_budget=config.get("monthly_token_budget", 1_000_000),
            monthly_api_calls=config.get("monthly_api_calls", 10_000),
            preferred_model=config.get("preferred_model", "openai/gpt-4o-mini"),
        )

    @app.post("/spaces/switch", response_model=SpaceResponse)
    async def switch_space(
        space_id: str,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
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
            if config.owner_id != principal.user_id and not principal.is_service:
                raise HTTPException(status_code=403, detail="Not authorized for this space.")
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
        principal: AuthPrincipal = Depends(get_optional_principal),
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
            if config.owner_id != principal.user_id and not principal.is_service:
                raise HTTPException(status_code=403, detail="Not authorized for this space.")
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
        principal: AuthPrincipal = Depends(get_optional_principal),
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
            if config.owner_id != principal.user_id and not principal.is_service:
                raise HTTPException(status_code=403, detail="Not authorized for this space.")
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

    @app.post("/spaces/{space_id}/wiki/lint", response_model=WikiLintResponse)
    async def lint_space_wiki(
        space_id: str,
        request: WikiLintRequest,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> WikiLintResponse:
        """Run wiki health checks for a space and optionally persist a report."""
        if not database_connected:
            raise HTTPException(status_code=503, detail="Database is not connected.")
        space_manager = SpaceManager(db)
        try:
            space_config = await space_manager.switch_space(space_id)
            if space_config.owner_id != principal.user_id and not principal.is_service:
                raise HTTPException(status_code=403, detail="Not authorized for this space.")
            space_obsidian = ObsidianClient(vault_path=space_config.obsidian_vault_path)
            lint_result = await orchestrator.lint_space_wiki(obsidian=space_obsidian, save_report=request.save_report)
            return WikiLintResponse(
                space_id=space_id,
                total_notes=lint_result.get("total_notes", 0),
                summary=lint_result.get("summary", {}),
                issues=lint_result.get("issues", {}),
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error running wiki lint: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/spaces/{space_id}")
    async def delete_space(
        space_id: str,
        permanently: bool = False,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, str]:
        """Delete or archive a space."""
        if not database_connected:
            raise HTTPException(
                status_code=503,
                detail="Database is not connected. Please check your DATABASE_URL configuration."
            )
        
        space_manager = SpaceManager(db)
        try:
            config = await space_manager.switch_space(space_id)
            if config.owner_id != principal.user_id and not principal.is_service:
                raise HTTPException(status_code=403, detail="Not authorized for this space.")
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

    @app.post("/settings/providers/key", response_model=ProviderKeyResponse)
    async def upsert_provider_key_endpoint(
        request: ProviderKeyUpsertRequest,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> ProviderKeyResponse:
        settings = get_settings()
        if not settings.secure_settings_enabled:
            raise HTTPException(status_code=404, detail="Secure provider settings are disabled.")
        owner_id = _assert_provider_owner(principal, request.owner_id)
        try:
            provider_key = await upsert_provider_key(
                db,
                owner_id=owner_id,
                provider=request.provider,
                api_key=request.api_key,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return ProviderKeyResponse(
            owner_id=provider_key.owner_id,
            provider=provider_key.provider,
            key_version=provider_key.key_version,
            last4=provider_key.last4,
            is_active=provider_key.is_active,
            updated_at=provider_key.updated_at.isoformat(),
        )

    @app.get("/settings/providers/key", response_model=ProviderKeyResponse)
    async def get_provider_key_status(
        provider: str,
        owner_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> ProviderKeyResponse:
        effective_owner_id = _assert_provider_owner(principal, owner_id)
        key = await db.scalar(
            select(ProviderCredential).where(
                ProviderCredential.owner_id == effective_owner_id,
                ProviderCredential.provider == provider,
            )
        )
        if key is None:
            raise HTTPException(status_code=404, detail="Provider key not configured.")
        return ProviderKeyResponse(
            owner_id=key.owner_id,
            provider=key.provider,
            key_version=key.key_version,
            last4=key.last4,
            is_active=key.is_active,
            updated_at=key.updated_at.isoformat(),
        )

    @app.post("/threads/create", response_model=ThreadResponse)
    async def create_thread(
        request: ThreadCreateRequest,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> ThreadResponse:
        effective_user_id = _effective_user_id(principal, request.user_id)
        thread = await _ensure_thread(
            db,
            user_id=effective_user_id,
            space_id=request.space_id,
            thread_id=None,
            title_hint=request.title,
        )
        return ThreadResponse(**thread.to_dict())

    @app.get("/threads/list", response_model=List[ThreadResponse])
    async def list_threads(
        user_id: Optional[str] = None,
        space_id: Optional[str] = None,
        include_archived: bool = False,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> List[ThreadResponse]:
        effective_user_id = _effective_user_id(principal, user_id)
        query = select(ConversationThread).where(ConversationThread.user_id == effective_user_id)
        if space_id is not None:
            query = query.where(ConversationThread.space_id == space_id)
        if not include_archived:
            query = query.where(ConversationThread.archived.is_(False))
        query = query.order_by(ConversationThread.updated_at.desc())
        rows = await db.scalars(query)
        return [ThreadResponse(**row.to_dict()) for row in rows.all()]

    @app.get("/threads/{thread_id}/messages", response_model=List[MessageResponse])
    async def list_thread_messages(
        thread_id: str,
        user_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> List[MessageResponse]:
        effective_user_id = _effective_user_id(principal, user_id)
        thread = await db.scalar(
            select(ConversationThread).where(
                ConversationThread.id == thread_id,
                ConversationThread.user_id == effective_user_id,
            )
        )
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found.")
        messages = await db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.thread_id == thread_id)
            .order_by(ConversationMessage.created_at.asc())
        )
        return [MessageResponse(**message.to_dict()) for message in messages.all()]

    @app.post("/threads/{thread_id}/rename", response_model=ThreadResponse)
    async def rename_thread(
        thread_id: str,
        request: ThreadRenameRequest,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> ThreadResponse:
        effective_user_id = _effective_user_id(principal, request.user_id)
        thread = await db.scalar(
            select(ConversationThread).where(
                ConversationThread.id == thread_id,
                ConversationThread.user_id == effective_user_id,
            )
        )
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found.")
        thread.title = request.title.strip()[:80] or "Untitled Thread"
        thread.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(thread)
        return ThreadResponse(**thread.to_dict())

    @app.post("/threads/{thread_id}/archive", response_model=ThreadResponse)
    async def archive_thread(
        thread_id: str,
        user_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> ThreadResponse:
        effective_user_id = _effective_user_id(principal, user_id)
        thread = await db.scalar(
            select(ConversationThread).where(
                ConversationThread.id == thread_id,
                ConversationThread.user_id == effective_user_id,
            )
        )
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found.")
        thread.archived = True
        thread.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(thread)
        return ThreadResponse(**thread.to_dict())

    @app.post("/obsidian/context/events")
    async def ingest_obsidian_context_event(
        request: ObsidianContextIngestRequest,
        http_request: Request,
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, Any]:
        _assert_obsidian_plugin_auth(http_request)
        effective_user_id = _effective_user_id(principal, request.user_id)
        now = datetime.utcnow()
        event = request.event
        normalized_type = (event.event_type or "").strip().lower()
        if normalized_type not in {"open", "click", "selection", "navigate"}:
            raise HTTPException(status_code=422, detail=f"Unsupported Obsidian event type: {event.event_type}")

        event_payload = {
            "event_id": event.event_id or str(uuid4()),
            "event_type": normalized_type,
            "note_path": event.note_path,
            "note_title": event.note_title,
            "selection": event.selection,
            "clicked_target": event.clicked_target,
            "cursor_line": event.cursor_line,
            "event_ts_ms": event.event_ts_ms or int(time.time() * 1000),
            "metadata": event.metadata or {},
            "received_at": now.isoformat(),
        }
        key = _obsidian_session_key(
            user_id=effective_user_id,
            space_id=request.space_id,
            session_id=request.session_id,
        )
        with _OBSIDIAN_CONTEXT_LOCK:
            session = _OBSIDIAN_CONTEXT_SESSIONS.get(key) or {
                "session_id": request.session_id or "default",
                "user_id": effective_user_id,
                "space_id": request.space_id,
                "active_note_path": None,
                "active_note_title": None,
                "active_selection": None,
                "recent_events": [],
                "last_event_at": None,
                "last_event_id": None,
            }
            if session.get("last_event_id") == event_payload["event_id"]:
                return {"status": "deduplicated", "session_id": session["session_id"]}
            session["last_event_id"] = event_payload["event_id"]
            session["active_note_path"] = event.note_path
            session["active_note_title"] = event.note_title or session.get("active_note_title")
            if event.selection is not None:
                session["active_selection"] = event.selection
            session["last_event_at"] = now.isoformat()
            session["last_heartbeat_at"] = now.isoformat()
            recent = list(session.get("recent_events") or [])
            recent.append(event_payload)
            session["recent_events"] = recent[-25:]
            _OBSIDIAN_CONTEXT_SESSIONS[key] = session
            recent_count = len(session["recent_events"])

        return {
            "status": "accepted",
            "session_id": request.session_id or "default",
            "active_note_path": event.note_path,
            "recent_events": recent_count,
        }

    @app.post("/obsidian/context/heartbeat")
    async def obsidian_context_heartbeat(
        request: ObsidianContextHeartbeatRequest,
        http_request: Request,
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, Any]:
        _assert_obsidian_plugin_auth(http_request)
        effective_user_id = _effective_user_id(principal, request.user_id)
        now = datetime.utcnow()
        key = _obsidian_session_key(
            user_id=effective_user_id,
            space_id=request.space_id,
            session_id=request.session_id,
        )
        with _OBSIDIAN_CONTEXT_LOCK:
            session = _OBSIDIAN_CONTEXT_SESSIONS.get(key) or {
                "session_id": request.session_id or "default",
                "user_id": effective_user_id,
                "space_id": request.space_id,
                "active_note_path": None,
                "active_note_title": None,
                "active_selection": None,
                "recent_events": [],
                "last_event_at": None,
                "last_event_id": None,
                "last_heartbeat_at": None,
            }
            session["last_heartbeat_at"] = now.isoformat()
            if request.active_note_path:
                session["active_note_path"] = request.active_note_path
            if request.active_note_title:
                session["active_note_title"] = request.active_note_title
            _OBSIDIAN_CONTEXT_SESSIONS[key] = session
        return {"status": "ok", "session_id": request.session_id or "default"}

    @app.get("/obsidian/context/session", response_model=ObsidianContextSessionResponse)
    async def get_obsidian_context_session(
        user_id: Optional[str] = None,
        space_id: Optional[str] = None,
        session_id: Optional[str] = None,
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> ObsidianContextSessionResponse:
        effective_user_id = _effective_user_id(principal, user_id)
        key = _obsidian_session_key(effective_user_id, space_id, session_id)
        now = datetime.utcnow()

        def _heartbeat_age_ms(value: Optional[str]) -> Optional[int]:
            if not value:
                return None
            try:
                then = datetime.fromisoformat(value)
                return int((now - then).total_seconds() * 1000)
            except Exception:
                return None

        with _OBSIDIAN_CONTEXT_LOCK:
            existing = _OBSIDIAN_CONTEXT_SESSIONS.get(key)
            if not existing:
                return ObsidianContextSessionResponse(
                    session_id=session_id or "default",
                    user_id=effective_user_id,
                    space_id=space_id,
                )
            heartbeat_age_ms = _heartbeat_age_ms(existing.get("last_heartbeat_at"))
            return ObsidianContextSessionResponse(
                **existing,
                plugin_connected=bool(heartbeat_age_ms is not None and heartbeat_age_ms <= 10_000),
                last_heartbeat_age_ms=heartbeat_age_ms,
            )

    @app.post("/obsidian/threads/link")
    async def link_thread_to_obsidian(
        request: ObsidianLinkRequest,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, Any]:
        effective_user_id = _effective_user_id(principal, request.user_id)
        thread = await db.scalar(
            select(ConversationThread).where(
                ConversationThread.id == request.thread_id,
                ConversationThread.user_id == effective_user_id,
            )
        )
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found.")
        messages = await db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.thread_id == request.thread_id)
            .order_by(ConversationMessage.created_at.asc())
        )
        transcript = "\n\n".join([f"## {m.role}\n{m.content}" for m in messages.all()])
        note_body = request.summary or f"# {thread.title}\n\n{transcript}"
        obsidian = ObsidianClient()
        await obsidian.upsert_note(request.note_path, note_body)
        return {
            "status": "linked",
            "note_path": request.note_path,
            "deep_link": f"obsidian://open?vault=main&file={request.note_path.replace(' ', '%20')}",
        }

    @app.post("/obsidian/index")
    async def index_obsidian(
        request: ObsidianIndexRequest,
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, Any]:
        _ = principal
        obsidian = ObsidianClient()
        indexed: Dict[str, int] = {}
        backlinks: Dict[str, List[str]] = {}
        for prefix in request.prefixes:
            notes = await obsidian.list_notes(prefix)
            indexed[prefix] = len(notes)
            for note in notes:
                content = await obsidian.read_note(note)
                refs = []
                for token in content.split("[["):
                    if "]]" in token:
                        refs.append(token.split("]]", 1)[0].split("|", 1)[0].strip())
                backlinks[note] = refs
        return {"status": "indexed", "indexed_counts": indexed, "backlinks": backlinks}

    @app.post("/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ):
        """Stream chat responses with real-time RPI workflow updates."""
        timer = TimingCollector()
        effective_user_id = _effective_user_id(principal, request.user_id)
        if not database_connected:
            raise HTTPException(status_code=503, detail="Database is not connected.")
        
        context_sources = None
        if request.context_sources:
            with timer.measure("parse_context_sources"):
                context_sources = _parse_context_sources_or_422(request.context_sources)
        
        space_manager = None
        if request.space_id:
            with timer.measure("switch_space"):
                space_manager = SpaceManager(db)
                try:
                    await space_manager.switch_space(request.space_id)
                except ValueError as e:
                    raise HTTPException(status_code=404, detail=str(e))
        
        async def generate_stream():
            try:
                yield _sse_event({"type": "start", "message": "Starting workflow..."})
                thread = await _ensure_thread(
                    db,
                    user_id=effective_user_id,
                    space_id=request.space_id,
                    thread_id=request.thread_id,
                    title_hint=request.query,
                )
                with timer.measure("process_query"):
                    result = await app.state.orchestrator.process_query(
                        user_id=effective_user_id,
                        query=request.query,
                        model=request.model,
                        provider=request.provider,
                        context_sources=context_sources,
                        db=db,
                        space_manager=space_manager,
                        thread_id=thread.id,
                    )
                if result.research:
                    yield _sse_event({"type": "research", "content": result.research})
                if result.plan:
                    yield _sse_event({"type": "plan", "content": result.plan})
                if result.research:
                    timer.add("emit_research", 0.1)
                if result.plan:
                    timer.add("emit_plan", 0.1)
                yield _sse_event({"type": "answer", "content": result.answer})
                stream_metadata = {
                    **result.metadata,
                    "api_timings_ms": timer.timings_ms,
                    "contract_version": CONTRACT_VERSION,
                    "thread_id": thread.id,
                    "obsidian_context_attached": any(
                        (src.type or "").upper() == "OBSIDIAN" for src in (context_sources or [])
                    ),
                }
                yield _sse_event({"type": "metadata", "data": stream_metadata})
                yield _sse_event({"type": "done"})
                log_timing_summary(logger, "chat_stream_completed", timer.timings_ms)
            except Exception as e:
                logger.error(f"Error in stream: {e}", exc_info=True)
                yield _sse_event({"type": "error", "message": str(e)})
        
        return StreamingResponse(generate_stream(), media_type="text/event-stream")

    @app.get("/workflow/{session_id}/agents")
    async def get_agent_activity(
        session_id: str,
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, Any]:
        """Get agent activity for a workflow session."""
        _ = principal
        # For now, return static agent info. In future, this can track real-time agent states
        return {
            "session_id": session_id,
            "agents": [
                {"name": "Researcher", "role": "Research Assistant", "status": "idle", "tools_used": []},
                {"name": "Planner", "role": "Implementation Planner", "status": "idle", "tools_used": []},
                {"name": "Implementer", "role": "Implementation Executor", "status": "idle", "tools_used": []},
            ],
            "workflow_stage": "idle",
        }

    @app.get("/spaces/{space_id}/visualization")
    async def get_space_visualization(
        space_id: str,
        month: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
        principal: AuthPrincipal = Depends(get_optional_principal),
    ) -> Dict[str, Any]:
        """Get visualization data for a space."""
        if not database_connected:
            raise HTTPException(status_code=503, detail="Database is not connected.")
        
        space_manager = SpaceManager(db)
        try:
            await space_manager.switch_space(space_id)
            space_config = space_manager.get_current_space()
            if space_config.owner_id != principal.user_id and not principal.is_service:
                raise HTTPException(status_code=403, detail="Not authorized for this space.")
            usage = await space_manager.get_space_usage(space_id, month=month)
            
            # Get memory connections (simplified - can be enhanced)
            from app.adapters.chroma import ChromaMemoryAdapter
            from app.config import get_settings
            settings = get_settings()
            memory = ChromaMemoryAdapter(
                host=settings.chroma_host,
                port=settings.chroma_port,
                collection_name=space_config.mem0_collection_name,
                persist_directory=settings.chroma_persist_dir,
            )
            
            # Sample recent memories for graph
            recent_memories = await memory.search(user_id="*", query="", limit=20)
            
            return {
                "space_id": space_id,
                "usage": {
                    "tokens_used": usage.tokens_used,
                    "api_calls_used": usage.api_calls_used,
                    "cost_usd": float(usage.cost_usd),
                    "tokens_remaining": usage.get_budget_remaining(space_config),
                },
                "memory_count": len(recent_memories),
                "memories": [{"id": i, "text": m.text[:100], "score": m.score} for i, m in enumerate(recent_memories)],
            }
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error getting space visualization: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    return app


app = create_app()
