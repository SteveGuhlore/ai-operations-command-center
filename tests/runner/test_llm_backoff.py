"""The model call backs off on Gemini/Vertex 429 RESOURCE_EXHAUSTED (the whole-universe sweep +
overnight rounds burst past the rate limit) instead of hard-failing the research task."""
import runner.agents.base as b


def _agent(client):
    ag = object.__new__(b.AgentBase)
    ag._use_vertex = False
    ag.model = "gemini-2.5-pro"
    ag.client = client
    return ag


def test_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setenv("TONY_LLM_RETRY_TRIES", "5")
    monkeypatch.setattr(b.time, "sleep", lambda s: None)
    calls = {"n": 0}

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**k):
                    calls["n"] += 1
                    if calls["n"] < 3:
                        raise Exception("Error code: 429 - RESOURCE_EXHAUSTED")
                    return "OK"

    assert _agent(Client())._completion_with_backoff(messages=[]) == "OK"
    assert calls["n"] == 3


def test_non_rate_limit_raises_immediately(monkeypatch):
    monkeypatch.setattr(b.time, "sleep", lambda s: None)
    calls = {"n": 0}

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**k):
                    calls["n"] += 1
                    raise Exception("Error code: 400 - bad request")

    import pytest
    with pytest.raises(Exception):
        _agent(Client())._completion_with_backoff(messages=[])
    assert calls["n"] == 1  # no retries on a non-429


def test_gives_up_after_max_tries(monkeypatch):
    monkeypatch.setenv("TONY_LLM_RETRY_TRIES", "3")
    monkeypatch.setattr(b.time, "sleep", lambda s: None)
    calls = {"n": 0}

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**k):
                    calls["n"] += 1
                    raise Exception("429 RESOURCE_EXHAUSTED")

    import pytest
    with pytest.raises(Exception):
        _agent(Client())._completion_with_backoff(messages=[])
    assert calls["n"] == 3  # exactly the cap, then re-raises
