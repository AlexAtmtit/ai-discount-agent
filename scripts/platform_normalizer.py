"""Platform payload normalizers and signature verification stubs.

These helpers normalize Instagram, TikTok, and WhatsApp webhook payloads
to the internal IncomingMessage shape used by the agent.

Signature verification is implemented as HMAC-SHA256 checks when the
corresponding env secret is present. In real deployments, ensure you use
the exact signature construction required by each provider.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any, Dict, Optional

from scripts.models import IncomingMessage


def _hmac_sha256(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_instagram_signature(headers: Dict[str, str], body: bytes) -> bool:
    """Verify Instagram/Meta signature if IG_APP_SECRET is set.

    Note: Real Meta signature is in X-Hub-Signature-256 with prefix "sha256=".
    """
    secret = os.getenv("IG_APP_SECRET")
    if not secret:
        return True
    sig = headers.get("x-hub-signature-256") or headers.get("X-Hub-Signature-256")
    if not sig or not sig.startswith("sha256="):
        return False
    expected = _hmac_sha256(secret, body)
    return hmac.compare_digest(sig.split("=", 1)[1], expected)


def verify_whatsapp_signature(headers: Dict[str, str], body: bytes) -> bool:
    """Verify WhatsApp signature if WHATSAPP_APP_SECRET is set.

    Also uses X-Hub-Signature-256 format.
    """
    secret = os.getenv("WHATSAPP_APP_SECRET")
    if not secret:
        return True
    sig = headers.get("x-hub-signature-256") or headers.get("X-Hub-Signature-256")
    if not sig or not sig.startswith("sha256="):
        return False
    expected = _hmac_sha256(secret, body)
    return hmac.compare_digest(sig.split("=", 1)[1], expected)


def verify_tiktok_signature(headers: Dict[str, str], body: bytes) -> bool:
    """Verify TikTok signature if TIKTOK_APP_SECRET is set.

    TikTok uses a timestamp + signature scheme; here we demo HMAC over body.
    """
    secret = os.getenv("TIKTOK_APP_SECRET")
    if not secret:
        return True
    sig = headers.get("x-tiktok-signature") or headers.get("X-TikTok-Signature")
    if not sig:
        return False
    expected = _hmac_sha256(secret, body)
    return hmac.compare_digest(sig, expected)


def normalize_instagram(payload: Dict[str, Any]) -> IncomingMessage:
    """Normalize Instagram/Meta webhook payload to IncomingMessage.

    Expected shape (simplified demo):
    {
      "entry": [{"messaging": [{
         "sender": {"id": "<user>"},
         "message": {"mid": "<message_id>", "text": "hi"},
         "timestamp": 1690000000
      }]}]
    }
    """
    try:
        msg = payload["entry"][0]["messaging"][0]
        user_id = msg["sender"]["id"]
        text = msg.get("message", {}).get("text", "")
        message_id = msg.get("message", {}).get("mid")
    except Exception:
        # Fallback minimal extraction
        user_id = str(payload.get("user_id") or payload.get("from", {}).get("id") or "unknown_user")
        text = payload.get("text") or payload.get("message", {}).get("text", "")
        message_id = payload.get("message_id")

    return IncomingMessage(platform="instagram", user_id=user_id, text=text or "", message_id=message_id)


def normalize_tiktok(payload: Dict[str, Any]) -> IncomingMessage:
    """Normalize TikTok webhook payload to IncomingMessage.

    Expected shape (simplified demo):
    {
      "messages": [{
        "sender": {"id": "<user>"},
        "id": "<message_id>",
        "text": "hello"
      }]
    }
    """
    try:
        msg = payload["messages"][0]
        user_id = msg["sender"]["id"]
        text = msg.get("text", "")
        message_id = msg.get("id")
    except Exception:
        user_id = str(payload.get("user_id") or payload.get("sender", {}).get("id") or "unknown_user")
        text = payload.get("text", "")
        message_id = payload.get("message_id")

    return IncomingMessage(platform="tiktok", user_id=user_id, text=text or "", message_id=message_id)


def normalize_whatsapp(payload: Dict[str, Any]) -> IncomingMessage:
    """Normalize WhatsApp Business webhook payload to IncomingMessage.

    Expected shape (simplified demo):
    {
      "contacts": [{"wa_id": "<user>"}],
      "messages": [{"id": "<message_id>", "text": {"body": "hi"}}]
    }
    """
    try:
        wa_id = payload["contacts"][0]["wa_id"]
        msg = payload["messages"][0]
        text = msg.get("text", {}).get("body", "")
        message_id = msg.get("id")
    except Exception:
        wa_id = str(payload.get("user_id") or "unknown_user")
        text = payload.get("text", "")
        message_id = payload.get("message_id")

    return IncomingMessage(platform="whatsapp", user_id=wa_id, text=text or "", message_id=message_id)

