from typing import List

from langchain_core.documents import Document

from app.core.memory import Memory
from app.core.types import LLMMessage
from app.domain.workflow import ResearchResult, PlanResult, ImplementResult


def memory_to_langchain_document(memory: Memory) -> Document:
    return Document(
        page_content=memory.text,
        metadata=memory.metadata,
    )


def langchain_document_to_memory(doc: Document) -> Memory:
    return Memory(
        text=doc.page_content,
        metadata=doc.metadata,
    )


def llm_messages_to_langchain(messages: List[LLMMessage]) -> List[dict]:
    return [{"role": msg.role, "content": msg.content} for msg in messages]


def langchain_response_to_domain(content: str, model: str) -> str:
    return content
