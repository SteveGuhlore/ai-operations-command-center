from runner.tools import tony_verdict as tv


def test_override_requires_target_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    r = tv.write_tony_verdict(symbol="X", tony_score=40, verdict="override", thesis="t")
    assert "error" in r and "target" in r["error"].lower()


def test_override_rejects_target_le_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    r = tv.write_tony_verdict(symbol="D", tony_score=30, verdict="override", thesis="t",
                              target=66.53, stop=66.53)
    assert "error" in r and "target > stop" in r["error"]


def test_adjust_with_levels_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    r = tv.write_tony_verdict(symbol="X", tony_score=70, verdict="adjust", thesis="t",
                              target=30.0, stop=25.0)
    assert r.get("success")


def test_reaffirm_allows_blank_levels(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    assert tv.write_tony_verdict(symbol="X", tony_score=80, verdict="reaffirm", thesis="t").get("success")


def test_bad_verdict_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    assert "error" in tv.write_tony_verdict(symbol="X", tony_score=80, verdict="buy", thesis="t")


def test_same_day_symbol_replaces(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    tv.write_tony_verdict(symbol="X", tony_score=50, verdict="pass", thesis="a")
    r = tv.write_tony_verdict(symbol="X", tony_score=90, verdict="reaffirm", thesis="b")
    assert r["total_verdicts"] == 1  # replaced, not stacked


def test_concurrent_writes_preserve_all(tmp_path, monkeypatch):
    # fan-out runs up to MAX_CONCURRENT ticker tasks at once, each calling write_tony_verdict on
    # the one shared file — the read-modify-write must be locked or verdicts get clobbered.
    import json
    import threading
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    (tmp_path / "v.json").write_text("[]")
    n = 24
    barrier = threading.Barrier(n)

    def w(i):
        barrier.wait()  # maximize contention
        tv.write_tony_verdict(symbol=f"S{i}", tony_score=50, verdict="reaffirm", thesis="t")

    threads = [threading.Thread(target=w, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    syms = {e["symbol"] for e in json.loads((tmp_path / "v.json").read_text())}
    assert len(syms) == n, f"lost verdicts under concurrency: {len(syms)}/{n}"
