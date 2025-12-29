"""Unit tests for Spaces functionality."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.spaces.space_model import SpaceConfig, SpaceStatus, SpaceUsage
from app.spaces.space_manager import SpaceManager
from app.models import SpaceRecord, SpaceUsageRecord


class TestSpaceConfig:
    """Test SpaceConfig dataclass."""

    def test_space_config_initialization(self) -> None:
        """Test basic SpaceConfig initialization."""
        config = SpaceConfig(
            space_id="test_space",
            name="Test Space",
            owner_id="user123",
        )
        assert config.space_id == "test_space"
        assert config.name == "Test Space"
        assert config.owner_id == "user123"
        assert config.status == SpaceStatus.ACTIVE

    def test_space_config_defaults(self) -> None:
        """Test SpaceConfig default values."""
        config = SpaceConfig(
            space_id="test_space",
            name="Test Space",
            owner_id="user123",
        )
        assert config.monthly_token_budget == 1_000_000
        assert config.monthly_api_calls == 10_000
        assert config.preferred_model == "openai/gpt-4o-mini"

    def test_space_config_auto_generated_paths(self) -> None:
        """Test that paths are auto-generated if not provided."""
        config = SpaceConfig(
            space_id="test_space",
            name="Test Space",
            owner_id="user123",
        )
        assert config.obsidian_vault_path == "./vaults/test_space"
        assert config.mem0_collection_name == "mem0_test_space"
        assert config.neo4j_graph_name == "graph_test_space"
        assert config.postgres_schema == "space_test_space"

    def test_space_config_custom_paths(self) -> None:
        """Test that custom paths are preserved."""
        config = SpaceConfig(
            space_id="test_space",
            name="Test Space",
            owner_id="user123",
            obsidian_vault_path="./custom/vault",
            mem0_collection_name="custom_collection",
        )
        assert config.obsidian_vault_path == "./custom/vault"
        assert config.mem0_collection_name == "custom_collection"


class TestSpaceUsage:
    """Test SpaceUsage dataclass."""

    def test_space_usage_budget_remaining(self) -> None:
        """Test budget remaining calculation."""
        config = SpaceConfig(
            space_id="test",
            name="Test",
            owner_id="user123",
            monthly_token_budget=100_000,
        )
        usage = SpaceUsage(
            space_id="test",
            month="2024-01",
            tokens_used=30_000,
        )
        assert usage.get_budget_remaining(config) == 70_000

    def test_space_usage_over_budget(self) -> None:
        """Test over budget check."""
        config = SpaceConfig(
            space_id="test",
            name="Test",
            owner_id="user123",
            monthly_token_budget=100_000,
        )
        usage = SpaceUsage(
            space_id="test",
            month="2024-01",
            tokens_used=150_000,
        )
        assert usage.is_over_budget(config) is True

    def test_space_usage_under_budget(self) -> None:
        """Test under budget check."""
        config = SpaceConfig(
            space_id="test",
            name="Test",
            owner_id="user123",
            monthly_token_budget=100_000,
        )
        usage = SpaceUsage(
            space_id="test",
            month="2024-01",
            tokens_used=50_000,
        )
        assert usage.is_over_budget(config) is False


class TestSpaceManager:
    """Test SpaceManager class."""

    @pytest.fixture
    def mock_db_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.delete = AsyncMock()
        return session

    @pytest.fixture
    def space_manager(self, mock_db_session) -> SpaceManager:
        """Create a SpaceManager instance."""
        return SpaceManager(mock_db_session)

    @pytest.mark.asyncio
    async def test_create_space_success(
        self, space_manager: SpaceManager, mock_db_session: AsyncMock
    ) -> None:
        """Test successful space creation."""
        # Mock database query to return no existing space
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        config = SpaceConfig(
            space_id="test_space",
            name="Test Space",
            owner_id="user123",
        )

        with patch("app.spaces.space_manager.Path") as mock_path, \
             patch("app.spaces.space_manager.chromadb") as mock_chroma, \
             patch("app.spaces.space_manager.engine") as mock_engine:
            # Mock directory creation
            mock_vault_path = MagicMock()
            mock_path.return_value = mock_vault_path
            mock_vault_path.mkdir = MagicMock()
            mock_vault_path.__truediv__ = MagicMock(return_value=mock_vault_path)

            # Mock Chroma client
            mock_chroma_client = MagicMock()
            mock_chroma.HttpClient.return_value = mock_chroma_client
            mock_chroma_client.get_or_create_collection = MagicMock()

            # Mock PostgreSQL schema creation
            mock_conn = AsyncMock()
            mock_engine.begin.return_value.__aenter__.return_value = mock_conn

            result = await space_manager.create_space(config)

            assert result.space_id == "test_space"
            assert result.name == "Test Space"
            assert space_manager.spaces_cache["test_space"] == config

    @pytest.mark.asyncio
    async def test_create_space_already_exists(
        self, space_manager: SpaceManager, mock_db_session: AsyncMock
    ) -> None:
        """Test space creation when space already exists."""
        # Mock database query to return existing space
        mock_result = MagicMock()
        mock_existing = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        mock_db_session.execute.return_value = mock_result

        config = SpaceConfig(
            space_id="test_space",
            name="Test Space",
            owner_id="user123",
        )

        with pytest.raises(ValueError, match="Space already exists"):
            await space_manager.create_space(config)

    @pytest.mark.asyncio
    async def test_switch_space_from_cache(
        self, space_manager: SpaceManager
    ) -> None:
        """Test switching to a space that's in cache."""
        config = SpaceConfig(
            space_id="test_space",
            name="Test Space",
            owner_id="user123",
        )
        space_manager.spaces_cache["test_space"] = config

        result = await space_manager.switch_space("test_space")

        assert result == config
        assert space_manager.current_space == config

    @pytest.mark.asyncio
    async def test_switch_space_from_database(
        self, space_manager: SpaceManager, mock_db_session: AsyncMock
    ) -> None:
        """Test switching to a space loaded from database."""
        # Mock database query to return space record
        mock_result = MagicMock()
        mock_record = MagicMock()
        mock_record.space_id = "test_space"
        mock_record.status = "active"
        mock_record.config = {
            "space_id": "test_space",
            "name": "Test Space",
            "owner_id": "user123",
            "monthly_token_budget": 1_000_000,
            "monthly_api_calls": 10_000,
            "obsidian_vault_path": "./vaults/test_space",
            "mem0_collection_name": "mem0_test_space",
            "neo4j_graph_name": "graph_test_space",
            "postgres_schema": "space_test_space",
            "preferred_model": "openai/gpt-4o-mini",
        }
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_db_session.execute.return_value = mock_result

        result = await space_manager.switch_space("test_space")

        assert result.space_id == "test_space"
        assert result.name == "Test Space"
        assert space_manager.current_space == result
        assert "test_space" in space_manager.spaces_cache

    @pytest.mark.asyncio
    async def test_switch_space_not_found(
        self, space_manager: SpaceManager, mock_db_session: AsyncMock
    ) -> None:
        """Test switching to a non-existent space."""
        # Mock database query to return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Space not found"):
            await space_manager.switch_space("nonexistent")

    def test_get_current_space_success(self, space_manager: SpaceManager) -> None:
        """Test getting current space when one is set."""
        config = SpaceConfig(
            space_id="test_space",
            name="Test Space",
            owner_id="user123",
        )
        space_manager.current_space = config

        result = space_manager.get_current_space()

        assert result == config

    def test_get_current_space_not_set(self, space_manager: SpaceManager) -> None:
        """Test getting current space when none is set."""
        with pytest.raises(RuntimeError, match="No space selected"):
            space_manager.get_current_space()

    @pytest.mark.asyncio
    async def test_list_spaces(
        self, space_manager: SpaceManager, mock_db_session: AsyncMock
    ) -> None:
        """Test listing spaces for an owner."""
        # Mock database query to return multiple space records
        mock_result = MagicMock()
        mock_record1 = MagicMock()
        mock_record1.space_id = "space1"
        mock_record1.status = "active"
        mock_record1.config = {
            "space_id": "space1",
            "name": "Space 1",
            "owner_id": "user123",
            "monthly_token_budget": 1_000_000,
            "monthly_api_calls": 10_000,
            "obsidian_vault_path": "./vaults/space1",
            "mem0_collection_name": "mem0_space1",
            "neo4j_graph_name": "graph_space1",
            "postgres_schema": "space_space1",
            "preferred_model": "openai/gpt-4o-mini",
        }
        mock_record2 = MagicMock()
        mock_record2.space_id = "space2"
        mock_record2.status = "active"
        mock_record2.config = {
            "space_id": "space2",
            "name": "Space 2",
            "owner_id": "user123",
            "monthly_token_budget": 500_000,
            "monthly_api_calls": 5_000,
            "obsidian_vault_path": "./vaults/space2",
            "mem0_collection_name": "mem0_space2",
            "neo4j_graph_name": "graph_space2",
            "postgres_schema": "space_space2",
            "preferred_model": "openai/gpt-4o-mini",
        }
        mock_result.scalars.return_value = [mock_record1, mock_record2]
        mock_db_session.execute.return_value = mock_result

        spaces = await space_manager.list_spaces("user123")

        assert len(spaces) == 2
        assert spaces[0].space_id == "space1"
        assert spaces[1].space_id == "space2"

    @pytest.mark.asyncio
    async def test_get_space_usage_existing(
        self, space_manager: SpaceManager, mock_db_session: AsyncMock
    ) -> None:
        """Test getting space usage when record exists."""
        # Mock database query to return usage record
        mock_result = MagicMock()
        mock_usage = MagicMock()
        mock_usage.space_id = "test_space"
        mock_usage.month = "2024-01"
        mock_usage.tokens_used = 50_000
        mock_usage.api_calls_used = 100
        mock_usage.cost_usd = 0.75
        mock_result.scalar_one_or_none.return_value = mock_usage
        mock_db_session.execute.return_value = mock_result

        usage = await space_manager.get_space_usage("test_space", "2024-01")

        assert usage.space_id == "test_space"
        assert usage.month == "2024-01"
        assert usage.tokens_used == 50_000
        assert usage.api_calls_used == 100
        assert usage.cost_usd == 0.75

    @pytest.mark.asyncio
    async def test_get_space_usage_not_found(
        self, space_manager: SpaceManager, mock_db_session: AsyncMock
    ) -> None:
        """Test getting space usage when record doesn't exist."""
        # Mock database query to return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        usage = await space_manager.get_space_usage("test_space", "2024-01")

        assert usage.space_id == "test_space"
        assert usage.month == "2024-01"
        assert usage.tokens_used == 0
        assert usage.api_calls_used == 0
        assert usage.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_update_space_usage_new_record(
        self, space_manager: SpaceManager, mock_db_session: AsyncMock
    ) -> None:
        """Test updating space usage when record doesn't exist."""
        # Mock database query to return None (no existing record)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        await space_manager.update_space_usage(
            space_id="test_space",
            tokens_used=10_000,
            api_calls_used=5,
            cost_usd=0.15,
        )

        # Verify new record was added
        assert mock_db_session.add.called

    @pytest.mark.asyncio
    async def test_update_space_usage_existing_record(
        self, space_manager: SpaceManager, mock_db_session: AsyncMock
    ) -> None:
        """Test updating space usage when record exists."""
        # Mock database query to return existing usage record
        mock_result = MagicMock()
        mock_usage = MagicMock()
        mock_usage.space_id = "test_space"
        mock_usage.month = "2024-01"
        mock_usage.tokens_used = 50_000
        mock_usage.api_calls_used = 100
        mock_usage.cost_usd = 0.75
        mock_result.scalar_one_or_none.return_value = mock_usage
        mock_db_session.execute.return_value = mock_result

        await space_manager.update_space_usage(
            space_id="test_space",
            tokens_used=10_000,
            api_calls_used=5,
            cost_usd=0.15,
        )

        # Verify values were updated
        assert mock_usage.tokens_used == 60_000
        assert mock_usage.api_calls_used == 105
        assert mock_usage.cost_usd == 0.90

    @pytest.mark.asyncio
    async def test_delete_space_archive(
        self, space_manager: SpaceManager, mock_db_session: AsyncMock
    ) -> None:
        """Test archiving a space."""
        # Mock database query to return space record
        mock_result = MagicMock()
        mock_record = MagicMock()
        mock_record.space_id = "test_space"
        mock_record.status = "active"
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_db_session.execute.return_value = mock_result

        await space_manager.delete_space("test_space", permanently=False)

        assert mock_record.status == SpaceStatus.ARCHIVED.value
        assert mock_db_session.commit.called

    @pytest.mark.asyncio
    async def test_delete_space_permanently(
        self, space_manager: SpaceManager, mock_db_session: AsyncMock
    ) -> None:
        """Test permanently deleting a space."""
        # Mock database query to return space record
        mock_result = MagicMock()
        mock_record = MagicMock()
        mock_record.space_id = "test_space"
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_db_session.execute.return_value = mock_result

        # Add to cache
        config = SpaceConfig(
            space_id="test_space",
            name="Test Space",
            owner_id="user123",
        )
        space_manager.spaces_cache["test_space"] = config
        space_manager.current_space = config

        await space_manager.delete_space("test_space", permanently=True)

        assert mock_db_session.delete.called
        assert "test_space" not in space_manager.spaces_cache
        assert space_manager.current_space is None
