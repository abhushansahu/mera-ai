"""Space management: models and manager for isolated project spaces."""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.config import get_settings
from app.models import SpaceRecord, SpaceUsageRecord

logger = logging.getLogger(__name__)


class SpaceStatus(Enum):
    """Status of a space."""
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class SpaceConfig:
    """Configuration blueprint for isolated context."""
    space_id: str
    name: str
    owner_id: str
    monthly_token_budget: int = 1_000_000
    monthly_api_calls: int = 10_000
    obsidian_vault_path: str = ""
    mem0_collection_name: str = ""
    neo4j_graph_name: str = ""
    postgres_schema: str = ""
    preferred_model: str = "openai/gpt-4o-mini"
    status: SpaceStatus = SpaceStatus.ACTIVE

    def __post_init__(self) -> None:
        """Auto-generate paths if not provided."""
        if not self.obsidian_vault_path:
            self.obsidian_vault_path = f"./vaults/{self.space_id}"
        if not self.mem0_collection_name:
            self.mem0_collection_name = f"mem0_{self.space_id}"
        if not self.neo4j_graph_name:
            self.neo4j_graph_name = f"graph_{self.space_id}"
        if not self.postgres_schema:
            self.postgres_schema = f"space_{self.space_id}"


@dataclass
class SpaceUsage:
    """Usage tracking for a space per month."""
    space_id: str
    month: str  # Format: "YYYY-MM"
    tokens_used: int = 0
    api_calls_used: int = 0
    cost_usd: float = 0.0

    def get_budget_remaining(self, config: SpaceConfig) -> int:
        """Calculate remaining token budget."""
        return config.monthly_token_budget - self.tokens_used

    def is_over_budget(self, config: SpaceConfig) -> bool:
        """Check if space has exceeded token budget."""
        return self.tokens_used > config.monthly_token_budget


class SpaceManager:
    """Gatekeeper for space operations."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db = db_session
        self.spaces_cache: Dict[str, SpaceConfig] = {}
        self.current_space: Optional[SpaceConfig] = None

    async def create_space(self, config: SpaceConfig) -> SpaceConfig:
        """Create new isolated space."""
        logger.info(f"Creating space: {config.space_id}")
        existing = await self.db.execute(select(SpaceRecord).where(SpaceRecord.space_id == config.space_id))
        if existing.scalar_one_or_none():
            raise ValueError(f"Space already exists: {config.space_id}")

        vault_path = Path(config.obsidian_vault_path)
        vault_path.mkdir(parents=True, exist_ok=True)
        for folder in ["Projects", "Learning", "Memories"]:
            (vault_path / folder).mkdir(exist_ok=True)

        settings = get_settings()
        if settings.chroma_host:
            chroma_client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        else:
            chroma_client = chromadb.PersistentClient(
                path=settings.chroma_persist_dir or "./chroma_db",
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        chroma_client.get_or_create_collection(name=config.mem0_collection_name, metadata={"hnsw:space": "cosine"})

        async with engine.begin() as conn:
            schema_name = config.postgres_schema.replace('"', '""')
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

        space_record = SpaceRecord(
            space_id=config.space_id,
            name=config.name,
            owner_id=config.owner_id,
            config={
                "space_id": config.space_id,
                "name": config.name,
                "owner_id": config.owner_id,
                "monthly_token_budget": config.monthly_token_budget,
                "monthly_api_calls": config.monthly_api_calls,
                "obsidian_vault_path": config.obsidian_vault_path,
                "mem0_collection_name": config.mem0_collection_name,
                "neo4j_graph_name": config.neo4j_graph_name,
                "postgres_schema": config.postgres_schema,
                "preferred_model": config.preferred_model,
            },
            status=config.status.value,
        )
        self.db.add(space_record)
        await self.db.commit()
        self.spaces_cache[config.space_id] = config
        logger.info(f"✓ Space created: {config.space_id}")
        return config

    async def switch_space(self, space_id: str) -> SpaceConfig:
        """Switch to different space."""
        if space_id in self.spaces_cache:
            config = self.spaces_cache[space_id]
            self.current_space = config
            logger.info(f"→ Switched to space: {space_id} (from cache)")
            return config

        result = await self.db.execute(select(SpaceRecord).where(SpaceRecord.space_id == space_id))
        space_record = result.scalar_one_or_none()
        if not space_record:
            raise ValueError(f"Space not found: {space_id}")

        config_dict = space_record.config
        config = SpaceConfig(
            space_id=config_dict["space_id"],
            name=config_dict["name"],
            owner_id=config_dict["owner_id"],
            monthly_token_budget=config_dict.get("monthly_token_budget", 1_000_000),
            monthly_api_calls=config_dict.get("monthly_api_calls", 10_000),
            obsidian_vault_path=config_dict.get("obsidian_vault_path", ""),
            mem0_collection_name=config_dict.get("mem0_collection_name", ""),
            neo4j_graph_name=config_dict.get("neo4j_graph_name", ""),
            postgres_schema=config_dict.get("postgres_schema", ""),
            preferred_model=config_dict.get("preferred_model", "openai/gpt-4o-mini"),
            status=SpaceStatus(space_record.status),
        )
        self.spaces_cache[space_id] = config
        self.current_space = config
        logger.info(f"→ Switched to space: {space_id}")
        return config

    def get_current_space(self) -> SpaceConfig:
        """Get current space configuration."""
        if not self.current_space:
            raise RuntimeError("No space selected. Call switch_space() first.")
        return self.current_space

    async def list_spaces(self, owner_id: str) -> List[SpaceConfig]:
        """List all spaces for an owner."""
        result = await self.db.execute(select(SpaceRecord).where(SpaceRecord.owner_id == owner_id))
        records = result.scalars().all()
        spaces = []
        for record in records:
            config_dict = record.config
            spaces.append(SpaceConfig(
                space_id=config_dict["space_id"],
                name=config_dict["name"],
                owner_id=config_dict["owner_id"],
                monthly_token_budget=config_dict.get("monthly_token_budget", 1_000_000),
                monthly_api_calls=config_dict.get("monthly_api_calls", 10_000),
                obsidian_vault_path=config_dict.get("obsidian_vault_path", ""),
                mem0_collection_name=config_dict.get("mem0_collection_name", ""),
                neo4j_graph_name=config_dict.get("neo4j_graph_name", ""),
                postgres_schema=config_dict.get("postgres_schema", ""),
                preferred_model=config_dict.get("preferred_model", "openai/gpt-4o-mini"),
                status=SpaceStatus(record.status),
            ))
        return spaces

    async def delete_space(self, space_id: str, permanently: bool = False) -> None:
        """Delete or archive a space."""
        result = await self.db.execute(select(SpaceRecord).where(SpaceRecord.space_id == space_id))
        space_record = result.scalar_one_or_none()
        if not space_record:
            raise ValueError(f"Space not found: {space_id}")

        if permanently:
            await self.db.delete(space_record)
            await self.db.commit()
            if space_id in self.spaces_cache:
                del self.spaces_cache[space_id]
            if self.current_space and self.current_space.space_id == space_id:
                self.current_space = None
            logger.info(f"✓ Space deleted permanently: {space_id}")
        else:
            space_record.status = SpaceStatus.ARCHIVED.value
            await self.db.commit()
            logger.info(f"✓ Space archived: {space_id}")

    async def get_space_usage(self, space_id: str, month: Optional[str] = None) -> SpaceUsage:
        """Get space usage for a specific month."""
        if month is None:
            now = datetime.utcnow()
            month = f"{now.year}-{now.month:02d}"

        result = await self.db.execute(
            select(SpaceUsageRecord).where(SpaceUsageRecord.space_id == space_id, SpaceUsageRecord.month == month)
        )
        usage_record = result.scalar_one_or_none()

        if usage_record:
            return SpaceUsage(
                space_id=usage_record.space_id,
                month=usage_record.month,
                tokens_used=usage_record.tokens_used,
                api_calls_used=usage_record.api_calls_used,
                cost_usd=float(usage_record.cost_usd),
            )
        return SpaceUsage(space_id=space_id, month=month)

    async def update_space_usage(
        self, space_id: str, tokens_used: int = 0, api_calls_used: int = 0, cost_usd: float = 0.0, month: Optional[str] = None
    ) -> None:
        """Update space usage tracking."""
        if month is None:
            now = datetime.utcnow()
            month = f"{now.year}-{now.month:02d}"

        result = await self.db.execute(
            select(SpaceUsageRecord).where(SpaceUsageRecord.space_id == space_id, SpaceUsageRecord.month == month)
        )
        usage_record = result.scalar_one_or_none()

        if usage_record:
            usage_record.tokens_used += tokens_used
            usage_record.api_calls_used += api_calls_used
            usage_record.cost_usd += cost_usd
        else:
            usage_record = SpaceUsageRecord(
                space_id=space_id, month=month, tokens_used=tokens_used, api_calls_used=api_calls_used, cost_usd=cost_usd
            )
            self.db.add(usage_record)
        await self.db.commit()
