"""Integration tests for real Obsidian REST API client."""

import pytest
from unittest.mock import patch, MagicMock

from app.obsidian_client import ObsidianClient


def test_obsidian_client_create_note_with_mock():
    """Test that create_note makes HTTP POST request to Obsidian REST API."""
    with patch("httpx.Client") as mock_client_class:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = ObsidianClient(base_url="http://localhost:27124", token="test-token")
        client.create_note(title="Test Note", content="Test content", tags=["test"])

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://localhost:27124/vault/create"
        assert "Authorization" in call_args[1]["headers"]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"
        assert call_args[1]["json"]["path"] == "Test Note.md"
        assert "Test content" in call_args[1]["json"]["content"]


def test_obsidian_client_search_with_mock():
    """Test that search makes HTTP POST request to Obsidian REST API."""
    with patch("httpx.Client") as mock_client_class:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            {"path": "note1.md", "content": "Content 1"},
            {"path": "note2.md", "content": "Content 2"},
        ]
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = ObsidianClient(base_url="http://localhost:27124", token="test-token")
        results = client.search(query="test query", limit=5)

        assert len(results) == 2
        assert results[0]["path"] == "note1.md"
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://localhost:27124/vault/search"
        assert call_args[1]["json"]["query"] == "test query"
        assert call_args[1]["json"]["limit"] == 5


def test_obsidian_client_handles_errors_gracefully():
    """Test that Obsidian client handles network errors gracefully."""
    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.side_effect = Exception("Network error")
        mock_client_class.return_value = mock_client

        client = ObsidianClient(base_url="http://localhost:27124")
        # Should not raise, but return empty list or do nothing
        results = client.search(query="test")
        assert results == []

        # create_note should not raise either
        client.create_note(title="Test", content="Content")

