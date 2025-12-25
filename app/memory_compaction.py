from datetime import datetime
from typing import Any, Dict, List

from app.llm_client import call_openrouter_chat
from app.memory_mem0 import Mem0Wrapper


async def compact_memories(
    mem0: Mem0Wrapper,
    user_id: str,
    model: str,
    now: datetime | None = None,
) -> Dict[str, Any]:
    """Compact a user's recent memories into a single snapshot.

    This is an async function that returns the snapshot and also stores it back
    into Mem0 for future retrieval.
    """
    raw: List[Dict[str, Any]] = await mem0.search(user_id=user_id, query="*", limit=50)
    if not raw:
        return {"snapshot": "", "source_count": 0}

    joined = "\n".join([r.get("text", "") for r in raw])
    prompt = (
        "You are compressing long-term conversation memory.\n\n"
        "Memories:\n"
        f"{joined}\n\n"
        "Create a concise, factual summary grouped into:\n"
        "1. USER_PROFILE\n2. PROJECTS\n3. LEARNINGS\n4. PREFERENCES\n"
    )
    summary = await call_openrouter_chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )

    timestamp = (now or datetime.utcnow()).isoformat()
    snapshot_text = f"[Snapshot at {timestamp}]\n\n{summary}"

    await mem0.store(
        user_id=user_id,
        text=snapshot_text,
        metadata={"type": "compacted_snapshot", "source_count": len(raw)},
    )

    return {"snapshot": snapshot_text, "source_count": len(raw)}


