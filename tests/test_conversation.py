import pytest

from scripts.agent_graph import run_agent_on_message
from scripts.store import get_store


@pytest.fixture(autouse=True)
def clear_store():
    get_store().clear_data()


def test_conversation_ask_then_creator():
    user = "conv_user_ask_then_creator"

    first = run_agent_on_message("discount", platform="instagram", user_id=user)
    assert first["database_row"]["conversation_status"] == "pending_creator_info"
    assert first["database_row"]["discount_code_sent"] is None

    second = run_agent_on_message("mkbhd", platform="instagram", user_id=user)
    assert second["database_row"]["conversation_status"] == "completed"
    assert second["database_row"]["identified_creator"] == "mkbhd"
    assert second["database_row"]["discount_code_sent"] == "MARQUES20"


def test_conversation_out_of_scope_then_creator():
    user = "conv_user_out_of_scope"

    first = run_agent_on_message("hello", platform="instagram", user_id=user)
    assert first["database_row"]["conversation_status"] == "out_of_scope"

    second = run_agent_on_message("casey", platform="instagram", user_id=user)
    assert second["database_row"]["conversation_status"] == "completed"
    assert second["database_row"]["identified_creator"] == "casey_neistat"
    assert "CASEY15OFF" in second["reply"]


def test_conversation_completed_then_resend_blocked():
    user = "conv_user_resend"

    first = run_agent_on_message("lily_singh sent me", platform="instagram", user_id=user)
    assert first["database_row"]["conversation_status"] == "completed"

    second = run_agent_on_message("mkbhd", platform="instagram", user_id=user)
    assert second["database_row"]["discount_code_sent"] is None
    assert "already" in second["reply"].lower()


def test_conversation_fuzzy_follow_up():
    user = "conv_user_fuzzy"

    first = run_agent_on_message("discount", platform="instagram", user_id=user)
    assert first["database_row"]["conversation_status"] == "pending_creator_info"

    second = run_agent_on_message("marques bronlee", platform="instagram", user_id=user)
    assert second["database_row"]["identified_creator"] == "mkbhd"
    assert "MARQUES20" in second["reply"]
