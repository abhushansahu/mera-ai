"""Space configuration models."""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


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
