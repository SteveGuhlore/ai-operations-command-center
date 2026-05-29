from runner.tools import landing


def _patch(monkeypatch, tmp_path):
    monkeypatch.setattr(landing, "LANDINGS_DIR", tmp_path)


def test_landing_absent_then_present(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    assert landing.landing_exists("ai-x") is False
    landing.write_landing_state("ai-x", status="draft")
    assert landing.landing_exists("ai-x") is True
    assert landing.read_landing_state("ai-x")["status"] == "draft"


def test_deploy_fields_persist(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    landing.write_landing_state("ai-x", status="draft")
    landing.write_landing_state("ai-x", status="deployed",
                                payment_link_url="https://buy.stripe.com/abc",
                                public_url="https://easysimplesites.org/ai-x")
    s = landing.read_landing_state("ai-x")
    assert s["status"] == "deployed"
    assert s["payment_link_url"].startswith("https://buy.stripe.com/")
