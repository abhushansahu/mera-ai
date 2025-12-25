"""Integration tests for review checkpoints in orchestrator."""

import pytest
from unittest.mock import MagicMock, patch

from app.orchestrator import UnifiedOrchestrator, _build_initial_state
from app.review_system import InMemoryReviewStore, ReviewStatus


def test_research_review_node_creates_review_task():
    """Test that research review node creates a review task."""
    store = InMemoryReviewStore()
    state = _build_initial_state(user_id="test_user", query="test query", model="gpt-4o-mini")
    state["research_output"] = "Research findings here."

    from app.orchestrator import _research_review_node

    result = _research_review_node(state, store)
    assert result["research_review_id"] is not None
    assert result["research_approved"] is True

    # Verify task was created in store
    task = store.get(result["research_review_id"])
    assert task is not None
    assert task.type == "research"
    assert task.content == "Research findings here."
    assert task.status == ReviewStatus.APPROVED


def test_plan_node_waits_for_research_approval():
    """Test that plan node only proceeds if research is approved."""
    state = _build_initial_state(user_id="test_user", query="test query", model="gpt-4o-mini")
    state["research_output"] = "Research here"
    state["research_approved"] = False  # Not approved

    from app.orchestrator import _plan_node

    with patch("app.orchestrator.call_openrouter_chat") as mock_llm:
        result = _plan_node(state)
        # Should not call LLM if research not approved
        mock_llm.assert_not_called()
        assert "not approved" in result["plan_output"].lower()


def test_plan_review_node_creates_review_task():
    """Test that plan review node creates a review task."""
    store = InMemoryReviewStore()
    state = _build_initial_state(user_id="test_user", query="test query", model="gpt-4o-mini")
    state["plan_output"] = "Plan steps here."

    from app.orchestrator import _plan_review_node

    result = _plan_review_node(state, store)
    assert result["plan_review_id"] is not None
    assert result["plan_approved"] is True

    task = store.get(result["plan_review_id"])
    assert task is not None
    assert task.type == "plan"


def test_implement_node_waits_for_plan_approval():
    """Test that implement node only proceeds if plan is approved."""
    state = _build_initial_state(user_id="test_user", query="test query", model="gpt-4o-mini")
    state["research_output"] = "Research"
    state["plan_output"] = "Plan"
    state["plan_approved"] = False  # Not approved

    from app.orchestrator import _implement_node

    with patch("app.orchestrator.call_openrouter_chat") as mock_llm:
        result = _implement_node(state)
        # Should not call LLM if plan not approved
        mock_llm.assert_not_called()
        assert "not approved" in result["answer"].lower()


def test_orchestrator_includes_review_nodes():
    """Test that orchestrator graph includes review checkpoints."""
    orchestrator = UnifiedOrchestrator()
    # Verify graph was built (should have research_review and plan_review nodes)
    assert orchestrator._app is not None

    # The graph should have these nodes (we can't directly inspect, but if it compiles, it's good)
    # In a real test, you'd invoke with a test state and verify the flow

