import json
import pytest
from fastapi.testclient import TestClient
import dashboard.server as server
from runner.tools import landing


@pytest.fixture
def client(tmp_path, monkeypatch):
    sites = tmp_path / "sites"
    (sites / "ai-x").mkdir(parents=True)
    (sites / "ai-x" / "index.html").write_text(
        '<a href="__STRIPE_PAYMENT_LINK__" class="cta">Buy</a>', encoding="utf-8")
    monkeypatch.setattr(landing, "LANDINGS_DIR", tmp_path / "landings")
    landing.write_landing_state("ai-x", status="draft")
    monkeypatch.setattr(server, "SITES_DIR", sites)
    monkeypatch.setattr(server, "UPSELL_CATALOG", tmp_path / "upsell-catalog.md")
    return TestClient(server.app)


def test_pending_lists_draft(client):
    r = client.get("/api/landing/pending")
    assert r.status_code == 200
    assert any(d["slug"] == "ai-x" for d in r.json()["pending"])


def test_deploy_injects_valid_stripe_url(client, tmp_path):
    r = client.post("/api/landing/deploy",
                    json={"slug": "ai-x", "payment_link_url": "https://buy.stripe.com/test_abc"})
    assert r.json()["success"] is True
    html = (tmp_path / "sites" / "ai-x" / "index.html").read_text()
    assert "https://buy.stripe.com/test_abc" in html
    assert "__STRIPE_PAYMENT_LINK__" not in html
    assert landing.read_landing_state("ai-x")["status"] == "deployed"
    catalog = (tmp_path / "upsell-catalog.md").read_text()
    assert "ai-x" in catalog


def test_deploy_rejects_non_stripe_url(client, tmp_path):
    r = client.post("/api/landing/deploy",
                    json={"slug": "ai-x", "payment_link_url": "https://evil.example.com/pay"})
    assert "error" in r.json()
    html = (tmp_path / "sites" / "ai-x" / "index.html").read_text()
    assert "__STRIPE_PAYMENT_LINK__" in html
    assert landing.read_landing_state("ai-x")["status"] == "draft"


def test_deploy_rejects_placeholder_passthrough(client):
    r = client.post("/api/landing/deploy",
                    json={"slug": "ai-x", "payment_link_url": "__STRIPE_PAYMENT_LINK__"})
    assert "error" in r.json()
