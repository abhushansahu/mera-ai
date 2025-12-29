from typing import List, Optional, Protocol

from app.core.types import Memory, UserID


class MemoryManager(Protocol):
    async def store(
        self,
        user_id: UserID,
        text: str,
        metadata: Optional[dict] = None,
    ) -> None:
        ...

    async def search(
        self,
        user_id: UserID,
        query: str,
        limit: int = 5,
    ) -> List[Memory]:
        ...
