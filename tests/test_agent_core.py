"""Core agent functionality tests

Tests for detection logic, agent responses, and basic integration.
Follows pytest conventions for clean, production-oriented testing.
"""

import pytest
from unittest.mock import patch

from scripts.agent_graph import run_agent_on_message, AIDiscountAgent
from scripts.models import ConversationStatus


def test_run_agent_on_message_exact_alias():
    """Test agent recognizes exact creator alias"""
    result = run_agent_on_message("mkbhd sent me")

    assert "MARQUES20" in result["reply"]
    assert result["database_row"]["identified_creator"] == "mkbhd"
    assert result["database_row"]["conversation_status"] == "completed"
    assert result["database_row"]["discount_code_sent"] == "MARQUES20"


def test_run_agent_on_message_casey():
    """Test agent recognizes Casey Neistat"""
    result = run_agent_on_message("Hello, Casey sent me here")

    assert "CASEY15OFF" in result["reply"]
    assert result["database_row"]["identified_creator"] == "casey_neistat"
    assert result["database_row"]["conversation_status"] == "completed"


def test_run_agent_on_message_no_creator():
    """Test agent asks for creator when none identified"""
    result = run_agent_on_message("discount please")

    assert "creator" in result["reply"].lower()
    assert result["database_row"]["identified_creator"] is None
    assert result["database_row"]["conversation_status"] == "pending_creator_info"
    assert result["database_row"]["discount_code_sent"] is None


def test_run_agent_on_message_out_of_scope():
    """Test agent handles out-of-scope messages"""
    result = run_agent_on_message("What's up?")

    assert "discount" in result["reply"].lower() or "creator" in result["reply"].lower()
    assert result["database_row"]["conversation_status"] == "out_of_scope"


def test_agent_idempotency_prevention():
    """Test one code per user per platform policy"""
    # First request should issue code
    result1 = run_agent_on_message("mkbhd", user_id="user123", platform="instagram")
    assert result1["database_row"]["discount_code_sent"] == "MARQUES20"

    # Second request should not issue new code
    result2 = run_agent_on_message("mkbhd", user_id="user123", platform="instagram")
    assert result2["database_row"]["discount_code_sent"] is None
    assert "already sent" in result2["reply"].lower()


def test_database_row_structure():
    """Test database row has required fields and structure"""
    result = run_agent_on_message("lily_singh sent me")
    row = result["database_row"]

    required_fields = [
        "user_id", "platform", "timestamp", "raw_incoming_message",
        "identified_creator", "discount_code_sent", "conversation_status"
    ]

    for field in required_fields:
        assert field in row

    # Check data types
    assert isinstance(row["user_id"], str)
    assert isinstance(row["platform"], str)
    assert isinstance(row["timestamp"], str)
    assert isinstance(row["raw_incoming_message"], str)
    assert len(row["timestamp"]) > 0
    assert row["timestamp"].endswith("Z")


def test_platform_handling():
    """Test different platforms are handled correctly"""
    result = run_agent_on_message("peter mckinnon", platform="tiktok", user_id="user456")

    assert result["database_row"]["platform"] == "tiktok"
    assert "PETERSVLOG" in result["reply"]


def test_creator_case_insensitive():
    """Test creator detection is case insensitive"""
    result = run_agent_on_message("CASEY_NEISTAT sent me")

    assert result["database_row"]["identified_creator"] == "casey_neistat"
    assert "CASEY15OFF" in result["reply"]


# Note: LLM fallback tests would require mocking google.generativeai
# Tests disabled by default to avoid API key requirements
@pytest.mark.optional
def test_llm_fallback_enabled():
    """Test LLM fallback when enabled (requires API key)"""
    with patch('scripts.agent_graph.get_gemini_client') as mock_client:
        # This would mock the LLM call - implementation for CI/CD
        pass
