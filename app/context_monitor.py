from typing import Any

import tiktoken


def _encoding():
    try:
        return tiktoken.encoding_for_model("gpt-4o")
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def estimate_tokens(content: Any) -> int:
    """Approximate token count for arbitrary content structures."""
    enc = _encoding()

    if isinstance(content, str):
        return len(enc.encode(content))
    if isinstance(content, dict):
        return len(enc.encode(str(content)))
    if isinstance(content, list):
        return sum(estimate_tokens(item) for item in content)
    return len(enc.encode(str(content)))


def context_utilization_percent(
    messages: list,
    extra: str | None = None,
    max_tokens: int = 128000,
    reserved_for_output: int = 8000,
) -> float:
    """Compute an approximate context window utilization percentage."""
    total_tokens = estimate_tokens(messages)
    if extra:
        total_tokens += estimate_tokens(extra)

    usable = max(max_tokens - reserved_for_output, 1)
    return (total_tokens / usable) * 100.0


