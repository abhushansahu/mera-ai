from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReviewTask as ReviewTaskModel


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ReviewTask:
    id: str
    user_id: str
    type: str  # "research" | "plan"
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer_notes: str = ""


class DatabaseReviewStore:
    """Database-backed review store with async support."""

    async def create(self, task: ReviewTask, db: AsyncSession) -> None:
        """Create a new review task in the database."""
        db_task = ReviewTaskModel(
            id=task.id,
            user_id=task.user_id,
            type=task.type,
            content=task.content,
            status=task.status.value,
            reviewer_notes=task.reviewer_notes,
            created_at=task.created_at,
            updated_at=task.created_at,
        )
        db.add(db_task)
        await db.commit()

    async def set_status(
        self, task_id: str, status: ReviewStatus, notes: str = "", db: AsyncSession = None
    ) -> None:
        """Update review task status."""
        if db is None:
            raise ValueError("Database session required")
        
        stmt = (
            update(ReviewTaskModel)
            .where(ReviewTaskModel.id == task_id)
            .values(status=status.value, reviewer_notes=notes, updated_at=datetime.utcnow())
        )
        await db.execute(stmt)
        await db.commit()

    async def get(self, task_id: str, db: AsyncSession) -> Optional[ReviewTask]:
        """Get a review task by ID."""
        stmt = select(ReviewTaskModel).where(ReviewTaskModel.id == task_id)
        result = await db.execute(stmt)
        db_task = result.scalar_one_or_none()
        
        if db_task is None:
            return None
        
        return ReviewTask(
            id=db_task.id,
            user_id=db_task.user_id,
            type=db_task.type,
            content=db_task.content,
            created_at=db_task.created_at,
            status=ReviewStatus(db_task.status),
            reviewer_notes=db_task.reviewer_notes,
        )


class InMemoryReviewStore:
    """Simple in-memory review store for personal use and tests.

    For real deployments, use DatabaseReviewStore with Postgres.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, ReviewTask] = {}

    async def create(self, task: ReviewTask, db: Optional[AsyncSession] = None) -> None:
        """Create a review task (in-memory)."""
        self._tasks[task.id] = task

    async def set_status(
        self, task_id: str, status: ReviewStatus, notes: str = "", db: Optional[AsyncSession] = None
    ) -> None:
        """Update review task status (in-memory)."""
        task = self._tasks.get(task_id)
        if not task:
            return
        task.status = status
        task.reviewer_notes = notes

    async def get(self, task_id: str, db: Optional[AsyncSession] = None) -> Optional[ReviewTask]:
        """Get a review task by ID (in-memory)."""
        return self._tasks.get(task_id)


