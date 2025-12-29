"""Integration tests for ChromaMemoryAdapter."""

import os
import pytest
import tempfile
import shutil
from typing import Dict, Any

from app.adapters.chroma import ChromaMemoryAdapter


@pytest.fixture
def temp_chroma_dir():
    """Create a temporary directory for Chroma data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def chroma_manager(temp_chroma_dir):
    """Create a ChromaMemoryAdapter instance for testing."""
    return ChromaMemoryAdapter(
        persist_directory=temp_chroma_dir,
        collection_name="test_memories",
    )


@pytest.mark.asyncio
async def test_store_and_search(chroma_manager: ChromaMemoryAdapter):
    """Test storing and searching memories."""
    user_id = "test_user"
    
    # Store a memory
    await chroma_manager.store(
        user_id=user_id,
        text="I love Python programming",
        metadata={"source": "test"},
    )
    
    # Search for it
    results = await chroma_manager.search(
        user_id=user_id,
        query="Python programming",
        limit=5,
    )
    
    assert len(results) > 0
    assert any("Python" in r.text for r in results)
    assert results[0].metadata.get("source") == "test"


@pytest.mark.asyncio
async def test_user_isolation(chroma_manager: ChromaMemoryAdapter):
    """Test that memories are isolated by user_id."""
    user1 = "user1"
    user2 = "user2"
    
    # Store memories for different users
    await chroma_manager.store(
        user_id=user1,
        text="User 1's secret information",
        metadata={"user": "1"},
    )
    await chroma_manager.store(
        user_id=user2,
        text="User 2's secret information",
        metadata={"user": "2"},
    )
    
    # Search as user1 - should only see user1's memories
    results1 = await chroma_manager.search(
        user_id=user1,
        query="secret",
        limit=5,
    )
    
    # Search as user2 - should only see user2's memories
    results2 = await chroma_manager.search(
        user_id=user2,
        query="secret",
        limit=5,
    )
    
    # Verify isolation
    assert all(r.metadata.get("user") == "1" for r in results1)
    assert all(r.metadata.get("user") == "2" for r in results2)
    assert len(results1) > 0
    assert len(results2) > 0


@pytest.mark.asyncio
async def test_metadata_filtering(chroma_manager: ChromaMemoryAdapter):
    """Test that metadata is stored and retrieved correctly."""
    user_id = "test_user"
    
    await chroma_manager.store(
        user_id=user_id,
        text="Test memory with metadata",
        metadata={
            "source": "test",
            "category": "example",
            "priority": "high",
        },
    )
    
    results = await chroma_manager.search(
        user_id=user_id,
        query="memory",
        limit=5,
    )
    
    assert len(results) > 0
    result = results[0]
    assert result.metadata.get("source") == "test"
    assert result.metadata.get("category") == "example"
    assert result.metadata.get("priority") == "high"


@pytest.mark.asyncio
async def test_search_limit(chroma_manager: ChromaMemoryAdapter):
    """Test that search respects the limit parameter."""
    user_id = "test_user"
    
    # Store multiple memories
    for i in range(10):
        await chroma_manager.store(
            user_id=user_id,
            text=f"Memory {i}: This is test memory number {i}",
            metadata={"index": i},
        )
    
    # Search with limit
    results = await chroma_manager.search(
        user_id=user_id,
        query="test memory",
        limit=3,
    )
    
    assert len(results) <= 3


@pytest.mark.asyncio
async def test_similarity_search(chroma_manager: ChromaMemoryAdapter):
    """Test that similarity search returns relevant results."""
    user_id = "test_user"
    
    # Store memories with different topics
    await chroma_manager.store(
        user_id=user_id,
        text="Python is a programming language",
        metadata={"topic": "programming"},
    )
    await chroma_manager.store(
        user_id=user_id,
        text="Dogs are loyal pets",
        metadata={"topic": "animals"},
    )
    await chroma_manager.store(
        user_id=user_id,
        text="JavaScript is used for web development",
        metadata={"topic": "programming"},
    )
    
    # Search for programming-related content
    results = await chroma_manager.search(
        user_id=user_id,
        query="programming languages",
        limit=5,
    )
    
    # Should return programming-related memories first
    assert len(results) > 0
    # At least one result should be about programming
    assert any("programming" in r.text.lower() or "Python" in r.text or "JavaScript" in r.text for r in results)


@pytest.mark.asyncio
async def test_empty_search(chroma_manager: ChromaMemoryAdapter):
    """Test searching when no memories exist."""
    user_id = "new_user"
    
    results = await chroma_manager.search(
        user_id=user_id,
        query="anything",
        limit=5,
    )
    
    # Should return empty list, not error
    assert isinstance(results, list)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_multiple_stores(chroma_manager: ChromaMemoryAdapter):
    """Test storing multiple memories for the same user."""
    user_id = "test_user"
    
    memories = [
        "First memory about Python",
        "Second memory about JavaScript",
        "Third memory about Rust",
    ]
    
    for memory in memories:
        await chroma_manager.store(
            user_id=user_id,
            text=memory,
            metadata={"source": "batch_test"},
        )
    
    # Search should return multiple results
    results = await chroma_manager.search(
        user_id=user_id,
        query="programming",
        limit=10,
    )
    
    assert len(results) >= 3
    texts = [r.text for r in results]
    assert any("Python" in text for text in texts)
    assert any("JavaScript" in text for text in texts)
