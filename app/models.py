from datetime import datetime
from typing import Any, Dict

from sqlalchemy import Column, DateTime, String, Text
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


class ReviewTask(Base):
    """Review task model for database persistence."""

    __tablename__ = "review_tasks"

    id = Column(String, primary_key=True)
    user_id = Column(String, index=True, nullable=False)
    type = Column(String, nullable=False)  # "research" | "plan"
    content = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending")  # "pending" | "approved" | "rejected"
    reviewer_notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "content": self.content,
            "status": self.status,
            "reviewer_notes": self.reviewer_notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

