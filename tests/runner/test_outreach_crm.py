"""log_outreach_lead — deterministic, append-only CRM persistence for the outreach pod."""
import importlib

import pytest


@pytest.fixture
def crm(tmp_path, monkeypatch):
    f = tmp_path / "crm.md"
    monkeypatch.setenv("OUTREACH_CRM_FILE", str(f))
    mod = importlib.import_module("runner.tools.outreach_crm")
    importlib.reload(mod)  # re-resolve CRM_FILE from the patched env
    return mod, f


def test_first_write_creates_file_with_header(crm):
    mod, f = crm
    res = mod.log_outreach_lead("Texture Salon", "Hair Salon", "Salem, MA",
                                "hi@texture.com", "email", "email_sent")
    assert res["success"]
    body = f.read_text()
    assert body.startswith("| Business | Type")
    assert "| Texture Salon | Hair Salon | Salem, MA | hi@texture.com | email | email_sent |" in body


def test_dedupe_by_business_name(crm):
    mod, f = crm
    mod.log_outreach_lead("Xiomara's Salon", status="email_sent")
    res = mod.log_outreach_lead("xiomara's salon", status="call_queued")  # case-insensitive dupe
    assert res.get("skipped") == "duplicate"
    assert f.read_text().count("Xiomara") == 1


def test_append_only_never_clobbers(crm):
    mod, f = crm
    mod.log_outreach_lead("A Biz", status="call_queued")
    mod.log_outreach_lead("B Biz", status="dm_queued")
    rows = [l for l in f.read_text().splitlines() if l.startswith("| ") and "Business" not in l and not l.startswith("|---")]
    assert len(rows) == 2


def test_invalid_status_rejected(crm):
    mod, _ = crm
    res = mod.log_outreach_lead("C Biz", status="interested_maybe")
    assert "error" in res


def test_missing_business_rejected(crm):
    mod, _ = crm
    assert "error" in mod.log_outreach_lead("", status="call_queued")


def test_pipes_in_fields_do_not_break_row(crm):
    mod, f = crm
    mod.log_outreach_lead("Bad|Name", "T|ype", status="call_queued")
    rows = [l for l in f.read_text().splitlines() if "Bad" in l]
    assert len(rows) == 1 and rows[0].count("|") == 9  # 8 cells -> 9 pipes, no extras
