import json
import hmac
import hashlib
import os

import pytest
from fastapi.testclient import TestClient

from api.app import app
from scripts.store import get_store


@pytest.fixture(autouse=True)
def clear_store():
    get_store().clear_data()


def _hmac_sha256_hex(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_webhook_instagram_e2e():
    client = TestClient(app)
    payload = {
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "ig_user_1"},
                        "message": {"mid": "m1", "text": "mkbhd sent me"},
                    }
                ]
            }
        ]
    }
    res = client.post("/webhook/instagram", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "MARQUES20" in data["reply"]
    row = data["database_row"]
    assert row["platform"] == "instagram"
    assert row["identified_creator"] == "mkbhd"
    assert row["conversation_status"] == "completed"


def test_webhook_tiktok_e2e():
    client = TestClient(app)
    payload = {
        "messages": [
            {
                "sender": {"id": "tt_user_1"},
                "id": "t1",
                "text": "casey discount",
            }
        ]
    }
    res = client.post("/webhook/tiktok", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "CASEY15OFF" in data["reply"]
    row = data["database_row"]
    assert row["platform"] == "tiktok"
    assert row["identified_creator"] == "casey_neistat"
    assert row["conversation_status"] == "completed"


def test_webhook_whatsapp_from_mention_e2e():
    client = TestClient(app)
    payload = {
        "contacts": [{"wa_id": "wa_user_1"}],
        "messages": [{"id": "w1", "text": {"body": "from @mkbhd"}}],
    }
    res = client.post("/webhook/whatsapp", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "MARQUES20" in data["reply"]
    row = data["database_row"]
    assert row["platform"] == "whatsapp"
    assert row["identified_creator"] == "mkbhd"


def test_instagram_signature_verification(monkeypatch):
    client = TestClient(app)
    secret = "ig_secret"
    monkeypatch.setenv("IG_APP_SECRET", secret)
    payload = {
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "ig_user_2"},
                        "message": {"mid": "m2", "text": "lily_singh"},
                    }
                ]
            }
        ]
    }
    body = json.dumps(payload).encode("utf-8")
    # Missing signature → 401
    res = client.post("/webhook/instagram", data=body, headers={"Content-Type": "application/json"})
    assert res.status_code == 401
    # Valid signature → 200
    sig = "sha256=" + _hmac_sha256_hex(secret, body)
    res2 = client.post(
        "/webhook/instagram",
        data=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
    )
    assert res2.status_code == 200


def test_whatsapp_signature_verification(monkeypatch):
    client = TestClient(app)
    secret = "wa_secret"
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)
    payload = {
        "contacts": [{"wa_id": "wa_user_2"}],
        "messages": [{"id": "w2", "text": {"body": "casey"}}],
    }
    body = json.dumps(payload).encode("utf-8")
    # Missing signature → 401
    res = client.post("/webhook/whatsapp", data=body, headers={"Content-Type": "application/json"})
    assert res.status_code == 401
    # Valid signature → 200
    sig = "sha256=" + _hmac_sha256_hex(secret, body)
    res2 = client.post(
        "/webhook/whatsapp",
        data=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
    )
    assert res2.status_code == 200


def test_tiktok_signature_verification(monkeypatch):
    client = TestClient(app)
    secret = "tt_secret"
    monkeypatch.setenv("TIKTOK_APP_SECRET", secret)
    payload = {
        "messages": [
            {
                "sender": {"id": "tt_user_2"},
                "id": "t2",
                "text": "peter_mckinnon discount",
            }
        ]
    }
    body = json.dumps(payload).encode("utf-8")
    # Missing signature → 401
    res = client.post("/webhook/tiktok", data=body, headers={"Content-Type": "application/json"})
    assert res.status_code == 401
    # Valid signature → 200
    sig = _hmac_sha256_hex(secret, body)
    res2 = client.post(
        "/webhook/tiktok",
        data=body,
        headers={"Content-Type": "application/json", "X-TikTok-Signature": sig},
    )
    assert res2.status_code == 200

