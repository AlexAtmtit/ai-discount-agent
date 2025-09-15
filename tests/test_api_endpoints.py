import pytest
from fastapi.testclient import TestClient

from api.app import app
from scripts.store import get_store
import yaml


@pytest.fixture(autouse=True)
def clear_store():
    get_store().clear_data()


def test_analytics_counts():
    client = TestClient(app)

    # Reset store
    r = client.post("/admin/reset")
    assert r.status_code == 200

    # Simulate some interactions
    client.post("/simulate", json={"platform": "instagram", "user_id": "u1", "message": "mkbhd"})
    client.post("/simulate", json={"platform": "instagram", "user_id": "u2", "message": "discount"})
    client.post("/simulate", json={"platform": "instagram", "user_id": "u2", "message": "casey"})

    # Analytics
    res = client.get("/analytics/creators")
    assert res.status_code == 200
    data = res.json()
    # total requests count only creators with identified_creator
    assert data["total_completed"] >= 2
    assert data["creators"]["mkbhd"]["codes_sent"] >= 1
    assert data["creators"]["casey_neistat"]["codes_sent"] >= 1
    # Per-platform breakdown now included; instagram should be present for these
    mkbhd_pb = data["creators"]["mkbhd"].get("platform_breakdown", {})
    assert "instagram" in mkbhd_pb
    assert mkbhd_pb["instagram"]["requests"] >= 1
    # codes_sent is aliased from completed
    assert mkbhd_pb["instagram"]["codes_sent"] >= 1


def test_admin_reload_updates_alias(tmp_path):
    client = TestClient(app)

    # Backup existing campaign config
    cfg_path = "config/campaign.yaml"
    original = open(cfg_path, "r").read()
    try:
        cfg = yaml.safe_load(original)
        # add a new alias for casey
        cfg["creators"]["casey_neistat"]["aliases"].append("cineboy")
        with open(cfg_path, "w") as f:
            yaml.safe_dump(cfg, f)

        # Reload
        r = client.post("/admin/reload")
        assert r.status_code == 200

        # New alias should work now
        res = client.post("/simulate", json={"platform": "instagram", "user_id": "u10", "message": "cineboy sent me"})
        assert res.status_code == 200
        out = res.json()
        assert out["database_row"]["identified_creator"] == "casey_neistat"
        assert "CASEY15OFF" in out["reply"]
    finally:
        with open(cfg_path, "w") as f:
            f.write(original)
