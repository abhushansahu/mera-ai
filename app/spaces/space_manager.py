"""Space manager for creating and managing isolated spaces."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.infrastructure.config.settings import get_settings
from app.spaces.space_model import SpaceConfig, SpaceStatus, SpaceUsage

logger = logging.getLogger(__name__)


class SpaceManager:
    """Gatekeeper for space operations."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize SpaceManager with database session."""
        self.db = db_session
        self.spaces_cache: Dict[str, SpaceConfig] = {}
        self.current_space: Optional[SpaceConfig] = None

    async def create_space(self, config: SpaceConfig) -> SpaceConfig:
        """Create new isolated space.

        Args:
            config: Space configuration

        Returns:
            Created space configuration

        Raises:
            ValueError: If space already exists
        """
        logger.info(f"Creating space: {config.space_id}")

        # Check if space already exists
        from app.models import SpaceRecord

        existing = await self.db.execute(
            select(SpaceRecord).where(SpaceRecord.space_id == config.space_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Space already exists: {config.space_id}")

        # Create Obsidian vault directory structure
        vault_path = Path(config.obsidian_vault_path)
        vault_path.mkdir(parents=True, exist_ok=True)
        for folder in ["Projects", "Learning", "Memories"]:
            (vault_path / folder).mkdir(exist_ok=True)

        # Create Chroma collection (space-specific)
        settings = get_settings()
        if settings.chroma_host:
            chroma_client = chromadb.HttpClient(
                host=settings.chroma_host, port=settings.chroma_port
            )
        else:
            chroma_client = chromadb.PersistentClient(
                path=settings.chroma_persist_dir or "./chroma_db",
                settings=ChromaSettings(anonymized_telemetry=False),
            )

        # Create or get collection for this space
        chroma_client.get_or_create_collection(
            name=config.mem0_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        # Create PostgreSQL schema
        async with engine.begin() as conn:
            # Use identifier quoting to prevent SQL injection
            schema_name = config.postgres_schema.replace('"', '""')
            await conn.execute(
                text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
            )

        # Store metadata in database
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

        # Cache the config
        self.spaces_cache[config.space_id] = config
        logger.info(f"✓ Space created: {config.space_id}")
        return config

    async def switch_space(self, space_id: str) -> SpaceConfig:
        """Switch to different space.

        Args:
            space_id: Space identifier

        Returns:
            Space configuration

        Raises:
            ValueError: If space not found
        """
        # Check cache first
        if space_id in self.spaces_cache:
            config = self.spaces_cache[space_id]
            self.current_space = config
            logger.info(f"→ Switched to space: {space_id} (from cache)")
            return config

        # Load from database
        from app.models import SpaceRecord

        result = await self.db.execute(
            select(SpaceRecord).where(SpaceRecord.space_id == space_id)
        )
        space_record = result.scalar_one_or_none()

        if not space_record:
            raise ValueError(f"Space not found: {space_id}")

        # Reconstruct SpaceConfig from database record
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

        # Cache and set as current
        self.spaces_cache[space_id] = config
        self.current_space = config
        logger.info(f"→ Switched to space: {space_id}")
        return config

    def get_current_space(self) -> SpaceConfig:
        """Get current space configuration.

        Returns:
            Current space configuration

        Raises:
            RuntimeError: If no space is currently selected
        """
        if not self.current_space:
            raise RuntimeError("No space selected. Call switch_space() first.")
        return self.current_space

    async def list_spaces(self, owner_id: str) -> List[SpaceConfig]:
        """List all spaces for an owner.

        Args:
            owner_id: Owner identifier

        Returns:
            List of space configurations
        """
        from app.models import SpaceRecord

        result = await self.db.execute(
            select(SpaceRecord).where(SpaceRecord.owner_id == owner_id)
        )
        records = result.scalars().all()

        spaces = []
        for record in records:
            config_dict = record.config
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
                status=SpaceStatus(record.status),
            )
            spaces.append(config)

        return spaces

    async def delete_space(
        self, space_id: str, permanently: bool = False
    ) -> None:
        """Delete or archive a space.

        Args:
            space_id: Space identifier
            permanently: If True, permanently delete. If False, archive.

        Raises:
            ValueError: If space not found
        """
        from app.models import SpaceRecord

        result = await self.db.execute(
            select(SpaceRecord).where(SpaceRecord.space_id == space_id)
        )
        space_record = result.scalar_one_or_none()

        if not space_record:
            raise ValueError(f"Space not found: {space_id}")

        if permanently:
            # Permanently delete
            await self.db.delete(space_record)
            await self.db.commit()
            if space_id in self.spaces_cache:
                del self.spaces_cache[space_id]
            if self.current_space and self.current_space.space_id == space_id:
                self.current_space = None
            logger.info(f"✓ Space deleted permanently: {space_id}")
        else:
            # Archive
            space_record.status = SpaceStatus.ARCHIVED.value
            await self.db.commit()
            logger.info(f"✓ Space archived: {space_id}")

    async def get_space_usage(
        self, space_id: str, month: Optional[str] = None
    ) -> SpaceUsage:
        """Get space usage for a specific month.

        Args:
            space_id: Space identifier
            month: Month in "YYYY-MM" format. If None, uses current month.

        Returns:
            Space usage record
        """
        if month is None:
            now = datetime.utcnow()
            month = f"{now.year}-{now.month:02d}"

        from app.models import SpaceUsageRecord

        result = await self.db.execute(
            select(SpaceUsageRecord).where(
                SpaceUsageRecord.space_id == space_id,
                SpaceUsageRecord.month == month,
            )
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
        else:
            # Return empty usage if not found
            return SpaceUsage(space_id=space_id, month=month)

    async def update_space_usage(
        self,
        space_id: str,
        tokens_used: int = 0,
        api_calls_used: int = 0,
        cost_usd: float = 0.0,
        month: Optional[str] = None,
    ) -> None:
        """Update space usage tracking.

        Args:
            space_id: Space identifier
            tokens_used: Additional tokens used
            api_calls_used: Additional API calls used
            cost_usd: Additional cost in USD
            month: Month in "YYYY-MM" format. If None, uses current month.
        """
        if month is None:
            now = datetime.utcnow()
            month = f"{now.year}-{now.month:02d}"

        from app.models import SpaceUsageRecord

        result = await self.db.execute(
            select(SpaceUsageRecord).where(
                SpaceUsageRecord.space_id == space_id,
                SpaceUsageRecord.month == month,
            )
        )
        usage_record = result.scalar_one_or_none()

        if usage_record:
            # Update existing record
            usage_record.tokens_used += tokens_used
            usage_record.api_calls_used += api_calls_used
            usage_record.cost_usd += cost_usd
        else:
            # Create new record
            usage_record = SpaceUsageRecord(
                space_id=space_id,
                month=month,
                tokens_used=tokens_used,
                api_calls_used=api_calls_used,
                cost_usd=cost_usd,
            )
            self.db.add(usage_record)

        await self.db.commit()
