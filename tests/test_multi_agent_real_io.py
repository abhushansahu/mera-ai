"""Integration tests for real I/O in multi-agent sub-agents."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.multi_agent_context_system import (
    ContextSource,
    ContextSourceType,
    MultiAgentCoordinator,
    FileExplorerAgent,
    LinkCrawlerAgent,
    DataAnalyzerAgent,
)


def test_file_explorer_agent_reads_real_files():
    """Test that FileExplorerAgent actually reads files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Hello, World!")

        coordinator = MultiAgentCoordinator.production()
        sources = [ContextSource(type=ContextSourceType.FILE, path=str(test_file))]

        result = coordinator.file_agent.run(sources, query="test")
        assert "test.txt" in result
        assert "Hello, World!" in result


def test_file_explorer_agent_reads_directories():
    """Test that FileExplorerAgent lists directory contents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "file1.txt").write_text("content1")
        (Path(tmpdir) / "file2.txt").write_text("content2")
        subdir = Path(tmpdir) / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("content3")

        coordinator = MultiAgentCoordinator.production()
        sources = [ContextSource(type=ContextSourceType.DIRECTORY, path=tmpdir)]

        result = coordinator.file_agent.run(sources, query="test")
        assert "file1.txt" in result
        assert "file2.txt" in result
        assert "subdir" in result or "file3.txt" in result


def test_link_crawler_agent_fetches_urls():
    """Test that LinkCrawlerAgent actually fetches URLs."""
    with patch("httpx.Client") as mock_client_class:
        mock_response = MagicMock()
        mock_response.text = "<html><body>Test Content</body></html>"
        mock_response.raise_for_status.return_value = None
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        coordinator = MultiAgentCoordinator.production()
        sources = [ContextSource(type=ContextSourceType.URL, path="https://example.com")]

        result = coordinator.link_agent.run(sources, query="test")
        assert "example.com" in result
        assert "Test Content" in result or "html" in result.lower()


def test_data_analyzer_agent_connects_to_database():
    """Test that DataAnalyzerAgent connects to databases."""
    # Use SQLite in-memory database for testing
    test_dsn = "sqlite:///:memory:"

    coordinator = MultiAgentCoordinator.production()
    sources = [ContextSource(type=ContextSourceType.DATABASE, path=test_dsn)]

    result = coordinator.data_agent.run(sources, query="test query")
    # Should contain database info (even if empty)
    assert "test query" in result.lower() or "database" in result.lower()


def test_production_coordinator_integrates_all_agents():
    """Test that production coordinator runs all agents and synthesizes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.md"
        test_file.write_text("# Test File\n\nContent here.")

        with patch("httpx.Client") as mock_client_class:
            mock_response = MagicMock()
            mock_response.text = "API Documentation"
            mock_response.raise_for_status.return_value = None
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.__exit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            from app.multi_agent_context_system import ContextSpecification

            coordinator = MultiAgentCoordinator.production()
            spec = ContextSpecification(
                query="Analyze this system",
                sources=[
                    ContextSource(type=ContextSourceType.FILE, path=str(test_file)),
                    ContextSource(type=ContextSourceType.URL, path="https://api.example.com/docs"),
                ],
            )

            result = coordinator.research_with_context(spec)
            assert "Research Summary" in result
            assert "Analyze this system" in result
            assert "test.md" in result or "Test File" in result
            assert "api.example.com" in result or "API Documentation" in result

