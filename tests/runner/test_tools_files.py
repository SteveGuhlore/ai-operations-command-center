import pytest
from pathlib import Path
from runner.tools import files as files_module


def test_read_file_returns_content(tmp_path, monkeypatch):
    monkeypatch.setattr(files_module, "WORKSPACE_DIR", tmp_path)
    (tmp_path / "notes.txt").write_text("hello world", encoding="utf-8")
    result = files_module.read_file(path="notes.txt")
    assert result["content"] == "hello world"


def test_read_file_rejects_path_outside_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(files_module, "WORKSPACE_DIR", tmp_path)
    result = files_module.read_file(path="../../etc/passwd")
    assert "error" in result


def test_write_file_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr(files_module, "WORKSPACE_DIR", tmp_path)
    result = files_module.write_file(path="output/report.txt", content="agent output")
    assert result["success"] is True
    assert (tmp_path / "output" / "report.txt").read_text() == "agent output"


def test_write_file_rejects_path_outside_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(files_module, "WORKSPACE_DIR", tmp_path)
    result = files_module.write_file(path="../../bad.txt", content="evil")
    assert "error" in result


def test_list_files_returns_names(tmp_path, monkeypatch):
    monkeypatch.setattr(files_module, "WORKSPACE_DIR", tmp_path)
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    result = files_module.list_files(directory=".")
    assert "a.txt" in result["files"]
    assert "b.txt" in result["files"]
