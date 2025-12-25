from datetime import datetime
from typing import Any, Dict

from app.llm_client import call_openrouter_chat
from app.obsidian_client import ObsidianClient


async def handle_error_with_learning(
    error: Exception,
    user_id: str,
    query: str,
    model: str,
    obsidian: ObsidianClient,
) -> Dict[str, Any]:
    """Create an error-learning note in Obsidian and return a safe response."""
    prompt = (
        "An internal error occurred while processing a user request.\n\n"
        f"User query:\n{query}\n\n"
        f"Error type: {type(error).__name__}\n"
        f"Error message: {str(error)}\n\n"
        "Explain, in markdown:\n"
        "1. Likely root cause (high level only, no stack traces).\n"
        "2. How this might be avoided in future.\n"
        "3. A short apology-style message suitable to show the user.\n"
    )
    analysis = await call_openrouter_chat(model=model, messages=[{"role": "user", "content": prompt}])

    title = f"Error Learning - {user_id} - {datetime.utcnow().isoformat()}"
    await obsidian.create_note(title=title, content=analysis, tags=["error-learning"])

    return {
        "safe_message": "Something went wrong while processing your request. "
        "I've logged the details to help improve future responses.",
        "analysis": analysis,
    }


