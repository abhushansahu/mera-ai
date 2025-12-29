from datetime import datetime
from typing import Any, Dict

from sqlalchemy import Column, DateTime, String, Text, Integer, Numeric, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB

from app.db import Base


class ConversationMessage(Base):
    """Minimal conversation message model for persistence.

    The schema is intentionally simple for now; it can be evolved later as
    the assistant gains features.
    """

    __tablename__ = "conversation_messages"

    id = Column(String, primary_key=True)
    user_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)  # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    message_metadata = Column("metadata", JSONB, nullable=False, default=dict)  # type: ignore[assignment]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "metadata": self.message_metadata or {},
        }


class SpaceRecord(Base):
    """Space metadata model for database persistence."""

    __tablename__ = "spaces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    space_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    owner_id = Column(String, nullable=False, index=True)
    config = Column(JSONB, nullable=False)  # type: ignore[assignment]
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "space_id": self.space_id,
            "name": self.name,
            "owner_id": self.owner_id,
            "config": self.config or {},
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class SpaceUsageRecord(Base):
    """Space usage tracking model for database persistence."""

    __tablename__ = "space_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    space_id = Column(String, nullable=False, index=True)
    month = Column(String, nullable=False)  # Format: "YYYY-MM"
    tokens_used = Column(Integer, nullable=False, default=0)
    api_calls_used = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Numeric(10, 2), nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("space_id", "month", name="uq_space_usage_space_month"),
        Index("idx_space_usage_space_month", "space_id", "month"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "space_id": self.space_id,
            "month": self.month,
            "tokens_used": self.tokens_used,
            "api_calls_used": self.api_calls_used,
            "cost_usd": float(self.cost_usd) if self.cost_usd else 0.0,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

