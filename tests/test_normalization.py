import pytest

from scripts.agent_graph import run_agent_on_message
from scripts.store import get_store


@pytest.fixture(autouse=True)
def clear_store():
    get_store().clear_data()


def assert_completed_for_creator(result, creator, code):
    row = result["database_row"]
    assert row["identified_creator"] == creator
    assert row["conversation_status"] == "completed"
    assert row["discount_code_sent"] == code


def test_normalization_trailing_punctuation():
    # Trailing punctuation removed
    result = run_agent_on_message("mkbhd!!!", platform="instagram", user_id="norm_user_1")
    assert_completed_for_creator(result, "mkbhd", "MARQUES20")


def test_normalization_whitespace_and_case():
    # Mixed case and excessive whitespace normalized
    result = run_agent_on_message("   MkBhD    SeNt   Me   ", platform="instagram", user_id="norm_user_2")
    assert_completed_for_creator(result, "mkbhd", "MARQUES20")


def test_normalization_hyphenation_alias():
    # Hyphen replaced with space; matches alias "casey neistat"
    result = run_agent_on_message("casey-neistat discount", platform="instagram", user_id="norm_user_3")
    assert_completed_for_creator(result, "casey_neistat", "CASEY15OFF")


def test_normalization_unicode_apostrophe():
    # Curly apostrophe should not block detection; "lily" alias triggers
    result = run_agent_on_message("Lily’s video discount", platform="instagram", user_id="norm_user_4")
    assert_completed_for_creator(result, "lily_singh", "LILY25")


def test_normalization_from_mention_with_comma():
    # From-mention heuristic with punctuation; should be in-scope and detect
    result = run_agent_on_message("I came from @mkbhd, need code", platform="instagram", user_id="norm_user_5")
    assert_completed_for_creator(result, "mkbhd", "MARQUES20")


def test_normalization_emoji_noise():
    # Emojis/noise should not prevent detection when alias present
    result = run_agent_on_message("mkbhd 😃🔥 sent me", platform="instagram", user_id="norm_user_6")
    assert_completed_for_creator(result, "mkbhd", "MARQUES20")

