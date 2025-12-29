"""Shared test fixtures and configuration."""

import pytest
from typing import AsyncGenerator

from app.adapters.chroma import ChromaMemoryAdapter
from app.adapters.openrouter import OpenRouterLLMAdapter
from app.domain.workflow import RPIWorkflow
from app.infrastructure.config.settings import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        openrouter_api_key="test_key",
        database_url="postgresql+psycopg2://test:test@localhost:5432/test",
        chroma_persist_dir="./test_chroma_db",
    )


@pytest.fixture
async def memory_adapter() -> AsyncGenerator[ChromaMemoryAdapter, None]:
    """Create a test memory adapter."""
    adapter = ChromaMemoryAdapter(
        persist_directory="./test_chroma_db",
        collection_name="test_memories",
    )
    yield adapter
    # Cleanup would go here


@pytest.fixture
def llm_adapter() -> OpenRouterLLMAdapter:
    """Create a test LLM adapter (mocked in tests)."""
    return OpenRouterLLMAdapter(api_key="test_key")


@pytest.fixture
def workflow(llm_adapter, memory_adapter) -> RPIWorkflow:
    """Create a test workflow."""
    return RPIWorkflow(llm=llm_adapter, memory=memory_adapter)
