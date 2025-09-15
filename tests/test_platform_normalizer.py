import pytest

from scripts.platform_normalizer import (
    normalize_instagram,
    normalize_tiktok,
    normalize_whatsapp,
)


def test_normalize_instagram_minimal():
    payload = {
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "ig_user_1"},
                        "message": {"mid": "m1", "text": "mkbhd sent me"},
                        "timestamp": 1690000000,
                    }
                ]
            }
        ]
    }
    m = normalize_instagram(payload)
    assert m.platform.value == "instagram"
    assert m.user_id == "ig_user_1"
    assert m.text == "mkbhd sent me"
    assert m.message_id == "m1"


def test_normalize_tiktok_minimal():
    payload = {
        "messages": [
            {
                "sender": {"id": "tt_user_1"},
                "id": "t1",
                "text": "casey discount",
            }
        ]
    }
    m = normalize_tiktok(payload)
    assert m.platform.value == "tiktok"
    assert m.user_id == "tt_user_1"
    assert m.text == "casey discount"
    assert m.message_id == "t1"


def test_normalize_whatsapp_minimal():
    payload = {
        "contacts": [{"wa_id": "wa_user_1"}],
        "messages": [{"id": "w1", "text": {"body": "from @mkbhd"}}],
    }
    m = normalize_whatsapp(payload)
    assert m.platform.value == "whatsapp"
    assert m.user_id == "wa_user_1"
    assert m.text == "from @mkbhd"
    assert m.message_id == "w1"

