import pytest
from runner.tasks import locker as locker_module


def test_acquire_lock_creates_lock_file(tmp_path, monkeypatch):
    monkeypatch.setattr(locker_module, "LOCKS_DIR", tmp_path)
    result = locker_module.acquire_lock("TASK-001", "debug_worker")
    assert result is True
    assert (tmp_path / "TASK-001.lock").exists()


def test_acquire_lock_fails_if_already_locked(tmp_path, monkeypatch):
    monkeypatch.setattr(locker_module, "LOCKS_DIR", tmp_path)
    locker_module.acquire_lock("TASK-001", "debug_worker")
    result = locker_module.acquire_lock("TASK-001", "heavy_worker")
    assert result is False


def test_release_lock_removes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(locker_module, "LOCKS_DIR", tmp_path)
    locker_module.acquire_lock("TASK-001", "debug_worker")
    locker_module.release_lock("TASK-001")
    assert not (tmp_path / "TASK-001.lock").exists()


def test_release_lock_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(locker_module, "LOCKS_DIR", tmp_path)
    locker_module.release_lock("TASK-999")  # no error on missing lock


def test_is_locked(tmp_path, monkeypatch):
    monkeypatch.setattr(locker_module, "LOCKS_DIR", tmp_path)
    assert locker_module.is_locked("TASK-001") is False
    locker_module.acquire_lock("TASK-001", "debug_worker")
    assert locker_module.is_locked("TASK-001") is True
