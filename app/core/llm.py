from typing import List, Protocol

from app.core.types import LLMMessage, LLMResponse


class LLMProvider(Protocol):
    async def chat(
        self,
        messages: List[LLMMessage],
        model: str,
        **kwargs,
    ) -> LLMResponse:
        ...
