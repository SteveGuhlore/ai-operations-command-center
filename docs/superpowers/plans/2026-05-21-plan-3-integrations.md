# Integrations — Implementation Plan 3 of 3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up Windows Task Scheduler for cron triggers, Tony Stocks file bridge from TradingBotAgentProject, Claude tool_use adapters (web search, file editor, code runner, image generation, audio generation), and plugin skill injection into agent system prompts.

**Architecture:** Tool adapters extend the runner's AgentBase to support multi-turn Claude tool_use loops — agents can call tools mid-task and get results back before producing final output. The scheduler registers four cron jobs in Windows Task Scheduler. The Tony bridge watches a shared folder and converts trading project output files into task queue entries. Plugin skills are loaded from the local Claude plugins cache at runner startup and injected as system prompt segments per agent role.

**Tech Stack:** Python 3.11+, anthropic SDK (tool_use), watchdog, Windows Task Scheduler (schtasks.exe). Prerequisite: Plans 1 and 2 complete.

---

## File Map

```
runner/
  agents/
    base.py              # MODIFY — add tool_use execution loop
    tool_runner.py       # NEW — dispatches tool calls to adapters
  tools/
    files.py             # NEW — workspace file read/write tool
    web.py               # NEW — web search + fetch tool
    code.py              # NEW — PowerShell subprocess tool
    image.py             # NEW — DALL-E 3 image generation tool
    audio.py             # NEW — OpenAI TTS audio generation tool
  bridge/
    __init__.py          # NEW
    tony_bridge.py       # NEW — watches bridge/tony-stocks/, creates tasks
  plugins/
    __init__.py          # NEW
    loader.py            # NEW — reads skill content from ~/.claude/plugins/cache
runner/scheduler/
  __init__.py            # NEW
  setup_windows.py       # NEW — registers cron jobs via schtasks.exe
bridge/
  tony-stocks/           # NEW empty folder (TradingBotAgentProject writes here)
tests/
  runner/
    test_tool_runner.py
    test_tools_files.py
    test_tools_web.py
    test_tools_code.py
    test_tony_bridge.py
    test_plugin_loader.py
```

---

## Task 1: Tool Runner + AgentBase tool_use Loop

**Files:**
- Create: `runner/agents/tool_runner.py`
- Modify: `runner/agents/base.py`
- Create: `tests/runner/test_tool_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_tool_runner.py
import pytest
from unittest.mock import MagicMock, patch
from runner.agents.tool_runner import dispatch_tool, TOOL_REGISTRY


def test_dispatch_tool_calls_registered_adapter():
    mock_adapter = MagicMock(return_value={"result": "ok"})
    with patch.dict(TOOL_REGISTRY, {"test_tool": mock_adapter}):
        result = dispatch_tool("test_tool", {"arg": "value"})
        mock_adapter.assert_called_once_with(arg="value")
        assert result == {"result": "ok"}


def test_dispatch_tool_raises_on_unknown_tool():
    with pytest.raises(ValueError, match="Unknown tool"):
        dispatch_tool("nonexistent_tool_xyz", {})


def test_dispatch_tool_returns_error_string_on_adapter_exception():
    def bad_adapter(**kwargs):
        raise RuntimeError("adapter failed")
    with patch.dict(TOOL_REGISTRY, {"bad_tool": bad_adapter}):
        result = dispatch_tool("bad_tool", {})
        assert "error" in str(result).lower()
```

- [ ] **Step 2: Run to verify they fail**

```powershell
python -m pytest tests/runner/test_tool_runner.py -v
```

Expected: 3 errors — module not found.

- [ ] **Step 3: Write `runner/agents/tool_runner.py`**

```python
# runner/agents/tool_runner.py
import json
from typing import Any, Callable

TOOL_REGISTRY: dict[str, Callable] = {}


def register_tool(name: str, adapter: Callable) -> None:
    TOOL_REGISTRY[name] = adapter


def dispatch_tool(tool_name: str, tool_input: dict) -> Any:
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {tool_name}")
    try:
        return TOOL_REGISTRY[tool_name](**tool_input)
    except Exception as exc:
        return {"error": str(exc)}
```

- [ ] **Step 4: Write the failing test for AgentBase tool_use loop**

```python
# append to tests/runner/test_tool_runner.py

from unittest.mock import patch, MagicMock
from runner.agents.base import AgentBase


def _make_tool_response(tool_name, tool_input, tool_use_id="tu_001"):
    tool_use = MagicMock()
    tool_use.type = "tool_use"
    tool_use.id = tool_use_id
    tool_use.name = tool_name
    tool_use.input = tool_input

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [tool_use]
    response.usage.input_tokens = 50
    response.usage.output_tokens = 20
    return response


def _make_final_response(text="Done."):
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text

    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [text_block]
    response.usage.input_tokens = 60
    response.usage.output_tokens = 30
    return response


def test_agent_executes_tool_use_loop():
    mock_tool = MagicMock(return_value={"content": "file contents here"})

    with patch("runner.agents.base.anthropic.Anthropic") as mock_anthropic_cls:
        with patch("runner.agents.base.record_spend"):
            with patch.dict("runner.agents.tool_runner.TOOL_REGISTRY", {"read_file": mock_tool}):
                mock_client = MagicMock()
                mock_anthropic_cls.return_value = mock_client
                mock_client.messages.create.side_effect = [
                    _make_tool_response("read_file", {"path": "README.md"}),
                    _make_final_response("Task complete."),
                ]

                tools_spec = [{
                    "name": "read_file",
                    "description": "Read a file",
                    "input_schema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    }
                }]

                agent = AgentBase(
                    "debug_worker", "claude-haiku-4-5", "You are Scout.",
                    tools=tools_spec
                )
                result = agent.run({"task_id": "T-001", "body": "Read README."})

                assert result["output"] == "Task complete."
                assert mock_client.messages.create.call_count == 2
                mock_tool.assert_called_once_with(path="README.md")
```

- [ ] **Step 5: Run to verify it fails**

```powershell
python -m pytest tests/runner/test_tool_runner.py::test_agent_executes_tool_use_loop -v
```

Expected: FAIL — AgentBase doesn't accept `tools` param yet.

- [ ] **Step 6: Modify `runner/agents/base.py` to support tool_use loop**

Replace the entire file:

```python
# runner/agents/base.py
import anthropic
from runner.ledger.budget import record_spend
from runner.agents.tool_runner import dispatch_tool

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-7":   (15.0, 75.0),
    "claude-sonnet-4-6": (3.0,  15.0),
    "claude-haiku-4-5":  (0.8,   4.0),
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = MODEL_PRICING.get(model, (3.0, 15.0))
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


class AgentBase:
    def __init__(
        self,
        role_id: str,
        model: str,
        system_prompt: str,
        tools: list[dict] | None = None,
    ):
        self.role_id = role_id
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.client = anthropic.Anthropic()

    def run(self, task: dict) -> dict:
        task_text = f"# Task: {task.get('task_id', 'unknown')}\n\n{task.get('body', '')}"
        messages = [{"role": "user", "content": task_text}]

        total_input = 0
        total_output = 0
        output_text = ""

        kwargs: dict = dict(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=messages,
        )
        if self.tools:
            kwargs["tools"] = self.tools

        while True:
            response = self.client.messages.create(**kwargs)
            total_input += response.usage.input_tokens
            total_output += response.usage.output_tokens

            if response.stop_reason == "end_turn":
                output_text = next(
                    (b.text for b in response.content if getattr(b, "type", None) == "text"),
                    "",
                )
                break

            if response.stop_reason == "tool_use":
                # Add assistant message with tool_use blocks
                messages.append({"role": "assistant", "content": response.content})

                # Execute each tool and collect results
                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        result = dispatch_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })

                messages.append({"role": "user", "content": tool_results})
                kwargs["messages"] = messages
                continue

            # Any other stop_reason — grab text and exit
            output_text = next(
                (b.text for b in response.content if getattr(b, "type", None) == "text"),
                str(response.content),
            )
            break

        cost = calculate_cost(self.model, total_input, total_output)
        record_spend(self.role_id, cost)

        return {
            "role_id": self.role_id,
            "task_id": task.get("task_id"),
            "output": output_text,
            "cost_usd": cost,
            "input_tokens": total_input,
            "output_tokens": total_output,
        }
```

- [ ] **Step 7: Run full test suite to verify nothing broke**

```powershell
python -m pytest tests/ -v --tb=short
```

Expected: All PASSED including the new tool_use test.

- [ ] **Step 8: Commit**

```powershell
git add runner\agents\tool_runner.py runner\agents\base.py tests\runner\test_tool_runner.py
git commit -m "feat: add tool_use loop to AgentBase and tool dispatcher"
```

---

## Task 2: File Tool Adapter

**Files:**
- Create: `runner/tools/files.py`
- Create: `tests/runner/test_tools_files.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_tools_files.py
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
```

- [ ] **Step 2: Run to verify they fail**

```powershell
python -m pytest tests/runner/test_tools_files.py -v
```

Expected: 5 errors — module not found.

- [ ] **Step 3: Write `runner/tools/files.py`**

```python
# runner/tools/files.py
from pathlib import Path

WORKSPACE_DIR = Path(__file__).parent.parent.parent / "workspace"


def _safe_path(relative: str) -> Path | None:
    target = (WORKSPACE_DIR / relative).resolve()
    if not str(target).startswith(str(WORKSPACE_DIR.resolve())):
        return None
    return target


def read_file(path: str) -> dict:
    safe = _safe_path(path)
    if safe is None:
        return {"error": f"Path outside workspace: {path}"}
    if not safe.exists():
        return {"error": f"File not found: {path}"}
    try:
        return {"content": safe.read_text(encoding="utf-8")}
    except OSError as exc:
        return {"error": str(exc)}


def write_file(path: str, content: str) -> dict:
    safe = _safe_path(path)
    if safe is None:
        return {"error": f"Path outside workspace: {path}"}
    try:
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.write_text(content, encoding="utf-8")
        return {"success": True, "path": str(safe)}
    except OSError as exc:
        return {"error": str(exc)}


def list_files(directory: str = ".") -> dict:
    safe = _safe_path(directory)
    if safe is None:
        return {"error": f"Path outside workspace: {directory}"}
    if not safe.is_dir():
        return {"error": f"Not a directory: {directory}"}
    return {"files": [f.name for f in sorted(safe.iterdir())]}


TOOL_SPEC = {
    "name": "file_editor",
    "description": "Read, write, or list files inside the workspace directory.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["read", "write", "list"]},
            "path": {"type": "string", "description": "Relative path inside workspace"},
            "content": {"type": "string", "description": "Content to write (only for write action)"},
        },
        "required": ["action", "path"],
    }
}


def file_editor(action: str, path: str, content: str = "") -> dict:
    if action == "read":
        return read_file(path)
    if action == "write":
        return write_file(path, content)
    if action == "list":
        return list_files(path)
    return {"error": f"Unknown action: {action}"}
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_tools_files.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Register the tool in tool_runner**

Add to the bottom of `runner/agents/tool_runner.py`:

```python
# Auto-register built-in tools at import time
from runner.tools.files import file_editor
register_tool("file_editor", file_editor)
```

- [ ] **Step 6: Commit**

```powershell
git add runner\tools\files.py runner\agents\tool_runner.py tests\runner\test_tools_files.py
git commit -m "feat: add file_editor tool adapter"
```

---

## Task 3: Web Research Tool Adapter

**Files:**
- Create: `runner/tools/web.py`
- Create: `tests/runner/test_tools_web.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_tools_web.py
import pytest
from unittest.mock import patch, MagicMock
from runner.tools.web import web_search, web_fetch, TOOL_SPEC


def test_web_search_returns_results():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Result 1\nResult 2")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 20
    mock_client.messages.create.return_value = mock_response

    with patch("runner.tools.web.anthropic.Anthropic", return_value=mock_client):
        result = web_search(query="python asyncio tutorial")
        assert "result" in result or "content" in result


def test_web_fetch_returns_content():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Page content here")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 20
    mock_client.messages.create.return_value = mock_response

    with patch("runner.tools.web.anthropic.Anthropic", return_value=mock_client):
        result = web_fetch(url="https://example.com")
        assert "content" in result or "result" in result


def test_tool_spec_has_required_fields():
    assert TOOL_SPEC["name"] == "web_research"
    assert "input_schema" in TOOL_SPEC
```

- [ ] **Step 2: Run to verify they fail**

```powershell
python -m pytest tests/runner/test_tools_web.py -v
```

Expected: 3 errors — module not found.

- [ ] **Step 3: Write `runner/tools/web.py`**

```python
# runner/tools/web.py
import anthropic

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def web_search(query: str) -> dict:
    client = _get_client()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": f"Search the web for: {query}. Summarise the top results briefly."}],
    )
    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), "")
    return {"content": text, "query": query}


def web_fetch(url: str) -> dict:
    client = _get_client()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2048,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": f"Fetch and summarise the content at this URL: {url}"}],
    )
    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), "")
    return {"content": text, "url": url}


def web_research(action: str, query: str = "", url: str = "") -> dict:
    if action == "search":
        return web_search(query)
    if action == "fetch":
        return web_fetch(url)
    return {"error": f"Unknown action: {action}"}


TOOL_SPEC = {
    "name": "web_research",
    "description": "Search the web or fetch a URL for current information.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["search", "fetch"]},
            "query": {"type": "string", "description": "Search query (for search action)"},
            "url": {"type": "string", "description": "URL to fetch (for fetch action)"},
        },
        "required": ["action"],
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_tools_web.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Register in tool_runner**

Add to the auto-register block at bottom of `runner/agents/tool_runner.py`:

```python
from runner.tools.web import web_research
register_tool("web_research", web_research)
```

- [ ] **Step 6: Commit**

```powershell
git add runner\tools\web.py runner\agents\tool_runner.py tests\runner\test_tools_web.py
git commit -m "feat: add web_research tool adapter"
```

---

## Task 4: Code Runner Tool Adapter

**Files:**
- Create: `runner/tools/code.py`
- Create: `tests/runner/test_tools_code.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_tools_code.py
import pytest
from runner.tools.code import run_powershell, TOOL_SPEC


def test_run_powershell_returns_stdout():
    result = run_powershell(command='Write-Output "hello"')
    assert result["stdout"].strip() == "hello"
    assert result["exit_code"] == 0


def test_run_powershell_captures_stderr():
    result = run_powershell(command="Get-Item C:\\nonexistent_path_xyz_abc")
    assert result["exit_code"] != 0 or "error" in result.get("stderr", "").lower() or result["stdout"] == ""


def test_run_powershell_times_out():
    result = run_powershell(command="Start-Sleep -Seconds 60", timeout=2)
    assert "timeout" in result.get("error", "").lower() or result["exit_code"] != 0


def test_forbidden_commands_are_blocked():
    for cmd in ["rm -rf /", "Remove-Item -Recurse -Force C:\\"]:
        result = run_powershell(command=cmd)
        assert "error" in result or result.get("blocked") is True


def test_tool_spec_has_required_fields():
    assert TOOL_SPEC["name"] == "code_runner"
    assert "input_schema" in TOOL_SPEC
```

- [ ] **Step 2: Run to verify they fail**

```powershell
python -m pytest tests/runner/test_tools_code.py -v
```

Expected: 5 errors — module not found.

- [ ] **Step 3: Write `runner/tools/code.py`**

```python
# runner/tools/code.py
import subprocess
import re

FORBIDDEN_PATTERNS = [
    r"rm\s+-rf",
    r"Remove-Item.*-Recurse.*-Force\s+[Cc]:\\?$",
    r"Format-Volume",
    r"Clear-Disk",
    r"dd\s+if=",
]

_FORBIDDEN_RE = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PATTERNS]


def _is_forbidden(command: str) -> bool:
    return any(pattern.search(command) for pattern in _FORBIDDEN_RE)


def run_powershell(command: str, timeout: int = 30) -> dict:
    if _is_forbidden(command):
        return {"blocked": True, "error": f"Command blocked by safety filter: {command[:80]}"}

    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "", "exit_code": -1, "error": "timeout exceeded"}
    except OSError as exc:
        return {"stdout": "", "stderr": "", "exit_code": -1, "error": str(exc)}


def code_runner(command: str, timeout: int = 30) -> dict:
    return run_powershell(command, timeout)


TOOL_SPEC = {
    "name": "code_runner",
    "description": "Run a PowerShell command in the workspace and return stdout/stderr.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "PowerShell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)", "default": 30},
        },
        "required": ["command"],
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_tools_code.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Register in tool_runner**

```python
from runner.tools.code import code_runner
register_tool("code_runner", code_runner)
```

- [ ] **Step 6: Commit**

```powershell
git add runner\tools\code.py runner\agents\tool_runner.py tests\runner\test_tools_code.py
git commit -m "feat: add code_runner tool adapter with safety filter"
```

---

## Task 5: Image Generation Tool Adapter

**Files:**
- Create: `runner/tools/image.py`
- Create: `tests/runner/test_tools_image.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_tools_image.py
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from runner.tools.image import generate_image, TOOL_SPEC


def test_generate_image_saves_file(tmp_path):
    mock_client = MagicMock()
    mock_image = MagicMock()
    mock_image.b64_json = "aGVsbG8="  # base64 "hello"
    mock_client.images.generate.return_value = MagicMock(data=[mock_image])

    with patch("runner.tools.image.openai.OpenAI", return_value=mock_client):
        with patch("runner.tools.image.OUTPUT_DIR", tmp_path):
            result = generate_image(prompt="a red circle", filename="test_image.png")
            assert result["success"] is True
            assert (tmp_path / "test_image.png").exists()


def test_generate_image_returns_error_on_api_failure():
    with patch("runner.tools.image.openai.OpenAI") as mock_cls:
        mock_cls.return_value.images.generate.side_effect = Exception("API error")
        result = generate_image(prompt="test", filename="out.png")
        assert "error" in result


def test_tool_spec_has_required_fields():
    assert TOOL_SPEC["name"] == "image_generation"
    assert "input_schema" in TOOL_SPEC
```

- [ ] **Step 2: Add openai to requirements.txt and install**

```
openai>=1.30.0
```

```powershell
pip install openai
```

- [ ] **Step 3: Run to verify tests fail**

```powershell
python -m pytest tests/runner/test_tools_image.py -v
```

Expected: 3 errors — module not found.

- [ ] **Step 4: Write `runner/tools/image.py`**

```python
# runner/tools/image.py
import base64
import openai
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "workspace" / "assets" / "images"


def generate_image(prompt: str, filename: str, size: str = "1024x1024") -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = openai.OpenAI()
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size=size,
            response_format="b64_json",
        )
        image_data = base64.b64decode(response.data[0].b64_json)
        out_path = OUTPUT_DIR / filename
        out_path.write_bytes(image_data)
        return {"success": True, "path": str(out_path), "prompt": prompt}
    except Exception as exc:
        return {"error": str(exc), "prompt": prompt}


def image_generation(prompt: str, filename: str, size: str = "1024x1024") -> dict:
    return generate_image(prompt, filename, size)


TOOL_SPEC = {
    "name": "image_generation",
    "description": "Generate an image using DALL-E 3 and save it to workspace/assets/images/.",
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "Detailed image generation prompt"},
            "filename": {"type": "string", "description": "Output filename, e.g. product-banner.png"},
            "size": {"type": "string", "enum": ["1024x1024", "1792x1024", "1024x1792"], "default": "1024x1024"},
        },
        "required": ["prompt", "filename"],
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_tools_image.py -v
```

Expected: 3 PASSED

- [ ] **Step 6: Register in tool_runner**

```python
from runner.tools.image import image_generation
register_tool("image_generation", image_generation)
```

- [ ] **Step 7: Commit**

```powershell
git add runner\tools\image.py runner\agents\tool_runner.py tests\runner\test_tools_image.py requirements.txt
git commit -m "feat: add image_generation tool adapter using DALL-E 3"
```

---

## Task 6: Audio Generation Tool Adapter

**Files:**
- Create: `runner/tools/audio.py`
- Create: `tests/runner/test_tools_audio.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_tools_audio.py
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from runner.tools.audio import generate_audio, TOOL_SPEC


def test_generate_audio_saves_file(tmp_path):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = b"fake_audio_bytes"
    mock_client.audio.speech.create.return_value = mock_response

    with patch("runner.tools.audio.openai.OpenAI", return_value=mock_client):
        with patch("runner.tools.audio.OUTPUT_DIR", tmp_path):
            result = generate_audio(text="Hello world", filename="intro.mp3")
            assert result["success"] is True
            assert (tmp_path / "intro.mp3").exists()


def test_generate_audio_returns_error_on_failure():
    with patch("runner.tools.audio.openai.OpenAI") as mock_cls:
        mock_cls.return_value.audio.speech.create.side_effect = Exception("TTS error")
        result = generate_audio(text="test", filename="out.mp3")
        assert "error" in result


def test_tool_spec_has_required_fields():
    assert TOOL_SPEC["name"] == "audio_generation"
```

- [ ] **Step 2: Run to verify they fail**

```powershell
python -m pytest tests/runner/test_tools_audio.py -v
```

Expected: 3 errors — module not found.

- [ ] **Step 3: Write `runner/tools/audio.py`**

```python
# runner/tools/audio.py
import openai
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "workspace" / "assets" / "audio"


def generate_audio(text: str, filename: str, voice: str = "alloy") -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = openai.OpenAI()
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
        )
        out_path = OUTPUT_DIR / filename
        out_path.write_bytes(response.content)
        return {"success": True, "path": str(out_path)}
    except Exception as exc:
        return {"error": str(exc)}


def audio_generation(text: str, filename: str, voice: str = "alloy") -> dict:
    return generate_audio(text, filename, voice)


TOOL_SPEC = {
    "name": "audio_generation",
    "description": "Generate speech audio using OpenAI TTS and save to workspace/assets/audio/.",
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "filename": {"type": "string", "description": "Output filename, e.g. intro.mp3"},
            "voice": {
                "type": "string",
                "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                "default": "alloy",
            },
        },
        "required": ["text", "filename"],
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_tools_audio.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Register in tool_runner**

```python
from runner.tools.audio import audio_generation
register_tool("audio_generation", audio_generation)
```

- [ ] **Step 6: Commit**

```powershell
git add runner\tools\audio.py runner\agents\tool_runner.py tests\runner\test_tools_audio.py
git commit -m "feat: add audio_generation tool adapter using OpenAI TTS"
```

---

## Task 7: Plugin Skill Loader

**Files:**
- Create: `runner/plugins/__init__.py`
- Create: `runner/plugins/loader.py`
- Create: `tests/runner/test_plugin_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_plugin_loader.py
import pytest
from pathlib import Path
from runner.plugins.loader import load_skill, build_agent_skills_prompt


def test_load_skill_returns_content(tmp_path, monkeypatch):
    import runner.plugins.loader as loader_module
    monkeypatch.setattr(loader_module, "PLUGINS_CACHE", tmp_path)
    skill_dir = tmp_path / "superpowers" / "5.1.0" / "skills" / "systematic-debugging"
    skill_dir.mkdir(parents=True)
    (skill_dir / "systematic-debugging.md").write_text("# Debug skill content", encoding="utf-8")
    result = load_skill("superpowers", "systematic-debugging")
    assert "Debug skill content" in result


def test_load_skill_returns_empty_when_missing(tmp_path, monkeypatch):
    import runner.plugins.loader as loader_module
    monkeypatch.setattr(loader_module, "PLUGINS_CACHE", tmp_path)
    result = load_skill("superpowers", "nonexistent-skill")
    assert result == ""


def test_build_agent_skills_prompt_for_debug_worker(tmp_path, monkeypatch):
    import runner.plugins.loader as loader_module
    monkeypatch.setattr(loader_module, "PLUGINS_CACHE", tmp_path)
    # No skills available — should return empty string gracefully
    result = build_agent_skills_prompt("debug_worker")
    assert isinstance(result, str)
```

- [ ] **Step 2: Run to verify they fail**

```powershell
python -m pytest tests/runner/test_plugin_loader.py -v
```

Expected: 3 errors — module not found.

- [ ] **Step 3: Create `runner/plugins/__init__.py` (empty)**

```powershell
"" | Out-File runner\plugins\__init__.py -Encoding utf8
```

- [ ] **Step 4: Write `runner/plugins/loader.py`**

```python
# runner/plugins/loader.py
from pathlib import Path

PLUGINS_CACHE = Path.home() / ".claude" / "plugins" / "cache" / "claude-plugins-official"

# Which skills to inject per agent role
AGENT_SKILLS: dict[str, list[tuple[str, str]]] = {
    "manager":                [("superpowers", "dispatching-parallel-agents")],
    "heavy_worker":           [("feature-dev", "feature-dev"), ("superpowers", "test-driven-development")],
    "debug_worker":           [("superpowers", "systematic-debugging"), ("code-review", "code-review")],
    "content_worker":         [],
    "media_worker":           [],
    "audio_worker":           [],
    "guard_worker":           [],
    "budget_worker":          [],
    "digital_product_worker": [("feature-dev", "feature-dev")],
    "marketing_worker":       [],
}


def _find_skill_file(plugin: str, skill: str) -> Path | None:
    plugin_dir = PLUGINS_CACHE / plugin
    if not plugin_dir.exists():
        return None
    # Find any version directory
    for version_dir in sorted(plugin_dir.iterdir(), reverse=True):
        candidate = version_dir / "skills" / skill / f"{skill}.md"
        if candidate.exists():
            return candidate
    return None


def load_skill(plugin: str, skill: str) -> str:
    path = _find_skill_file(plugin, skill)
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def build_agent_skills_prompt(role_id: str) -> str:
    skills = AGENT_SKILLS.get(role_id, [])
    parts = []
    for plugin, skill in skills:
        content = load_skill(plugin, skill)
        if content:
            parts.append(f"--- SKILL: {skill} ---\n{content}")
    return "\n\n".join(parts)
```

- [ ] **Step 5: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_plugin_loader.py -v
```

Expected: 3 PASSED

- [ ] **Step 6: Wire skill injection into `runner/agents/prompts.py`**

Add at the end of `build_system_prompt` in `runner/agents/prompts.py`:

```python
# At top of file, add:
from runner.plugins.loader import build_agent_skills_prompt

# In build_system_prompt, before the final return, add:
    skills_content = build_agent_skills_prompt(role_id)
    if skills_content:
        parts.append(f"\n\n## Workflow Skills\n\n{skills_content}")
```

The full updated function signature in `runner/agents/prompts.py`:

```python
def build_system_prompt(role_id: str) -> str:
    config = _get_agent_config(role_id)
    md = _load_agent_md(role_id)

    parts = []
    if md:
        parts.append(md)

    display_name = config.get("display_name", role_id)
    purpose = config.get("purpose", "")
    allowed_types = config.get("allowed_task_types", [])

    parts.append(f"Your role: {role_id}")
    parts.append(f"Display name: {display_name}")
    if purpose:
        parts.append(f"Purpose: {purpose}")
    if allowed_types:
        parts.append(f"Allowed task types: {', '.join(allowed_types)}")

    parts.append(
        "\nComplete the assigned task fully. Write your output clearly and concisely. "
        "Begin immediately — do not explain what you are about to do, just do it."
    )

    skills_content = build_agent_skills_prompt(role_id)
    if skills_content:
        parts.append(f"\n## Workflow Skills\n\n{skills_content}")

    return "\n\n".join(parts)
```

- [ ] **Step 7: Run full test suite**

```powershell
python -m pytest tests/ -v --tb=short
```

Expected: All PASSED.

- [ ] **Step 8: Commit**

```powershell
git add runner\plugins\ tests\runner\test_plugin_loader.py runner\agents\prompts.py
git commit -m "feat: add plugin skill loader and inject skills into agent system prompts"
```

---

## Task 8: Tony Stocks Bridge

**Files:**
- Create: `runner/bridge/__init__.py`
- Create: `runner/bridge/tony_bridge.py`
- Create: `bridge/tony-stocks/.gitkeep`
- Create: `tests/runner/test_tony_bridge.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_tony_bridge.py
import json
from pathlib import Path
from datetime import date
from runner.bridge import tony_bridge as bridge_module


SAMPLE_SCANNER = {
    "date": "2026-05-21",
    "type": "scanner",
    "tickers": ["AAPL", "TSLA"],
    "notes": "High momentum setups identified.",
}


def test_scanner_file_creates_task(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "bridge" / "tony-stocks"
    tasks_dir = tmp_path / "workspace" / "tasks" / "todo"
    bridge_dir.mkdir(parents=True)
    tasks_dir.mkdir(parents=True)

    monkeypatch.setattr(bridge_module, "BRIDGE_DIR", bridge_dir)
    monkeypatch.setattr(bridge_module, "TASKS_DIR", tasks_dir)

    scanner_file = bridge_dir / f"scanner-{date.today()}.json"
    scanner_file.write_text(json.dumps(SAMPLE_SCANNER), encoding="utf-8")

    bridge_module.process_bridge_file(scanner_file)

    task_files = list(tasks_dir.glob("*.md"))
    assert len(task_files) == 1
    content = task_files[0].read_text(encoding="utf-8")
    assert "stock_research_pod" in content
    assert "AAPL" in content


def test_process_bridge_file_skips_unknown_type(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "bridge"
    tasks_dir = tmp_path / "tasks"
    bridge_dir.mkdir()
    tasks_dir.mkdir()
    monkeypatch.setattr(bridge_module, "BRIDGE_DIR", bridge_dir)
    monkeypatch.setattr(bridge_module, "TASKS_DIR", tasks_dir)

    bad_file = bridge_dir / "unknown-2026-05-21.json"
    bad_file.write_text(json.dumps({"type": "unknown", "data": {}}))
    bridge_module.process_bridge_file(bad_file)  # should not raise or create tasks
    assert len(list(tasks_dir.glob("*.md"))) == 0


def test_scan_and_process_handles_multiple_files(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "bridge"
    tasks_dir = tmp_path / "tasks"
    bridge_dir.mkdir()
    tasks_dir.mkdir()
    monkeypatch.setattr(bridge_module, "BRIDGE_DIR", bridge_dir)
    monkeypatch.setattr(bridge_module, "TASKS_DIR", tasks_dir)

    for i in range(3):
        f = bridge_dir / f"scanner-2026-05-{i+1:02d}.json"
        f.write_text(json.dumps({**SAMPLE_SCANNER, "date": f"2026-05-{i+1:02d}"}))

    bridge_module.scan_and_process()
    assert len(list(tasks_dir.glob("*.md"))) == 3
```

- [ ] **Step 2: Run to verify they fail**

```powershell
python -m pytest tests/runner/test_tony_bridge.py -v
```

Expected: 3 errors — module not found.

- [ ] **Step 3: Create `runner/bridge/__init__.py` (empty)**

```powershell
New-Item -ItemType Directory -Force runner\bridge
"" | Out-File runner\bridge\__init__.py -Encoding utf8
New-Item -ItemType Directory -Force bridge\tony-stocks
"" | Out-File bridge\tony-stocks\.gitkeep -Encoding utf8
```

- [ ] **Step 4: Write `runner/bridge/tony_bridge.py`**

```python
# runner/bridge/tony_bridge.py
import json
import time
from pathlib import Path

BRIDGE_DIR = Path(__file__).parent.parent.parent / "bridge" / "tony-stocks"
TASKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "tasks" / "todo"

_PROCESSED_LOG = Path(__file__).parent.parent.parent / "workspace" / "logs" / "tony-bridge-processed.json"

TASK_TEMPLATES = {
    "scanner": (
        "market_scan_summary",
        "Scanner Summary — {date}",
        "Summarise the following scanner output. Identify top setups, note momentum signals, and produce a brief research note.\n\n{content}",
    ),
    "watchlist": (
        "watchlist_review",
        "Watchlist Review — {date}",
        "Review the following watchlist data. Note which tickers are showing strength or weakness and summarise key observations.\n\n{content}",
    ),
    "paper-trade": (
        "paper_trade_journal_summary",
        "Paper Trade Journal — {date}",
        "Summarise the following paper trade journal entries. Note wins, losses, and lessons.\n\n{content}",
    ),
}


def _load_processed() -> set:
    if not _PROCESSED_LOG.exists():
        return set()
    try:
        return set(json.loads(_PROCESSED_LOG.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return set()


def _save_processed(processed: set) -> None:
    _PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    _PROCESSED_LOG.write_text(json.dumps(sorted(processed)), encoding="utf-8")


def process_bridge_file(path: Path) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    file_type = data.get("type", "")
    # Detect type from filename if not in data
    if not file_type:
        stem = path.stem
        for key in TASK_TEMPLATES:
            if stem.startswith(key):
                file_type = key
                break

    if file_type not in TASK_TEMPLATES:
        return

    task_type, title_tpl, body_tpl = TASK_TEMPLATES[file_type]
    date_str = data.get("date", path.stem.split("-", 1)[-1] if "-" in path.stem else "unknown")
    content = json.dumps(data, indent=2)

    task_id = f"TONY-{file_type.upper()}-{date_str.replace('-', '')}"
    title = title_tpl.format(date=date_str)
    body = body_tpl.format(date=date_str, content=content)

    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_file = TASKS_DIR / f"{task_id}-tony-bridge.md"

    task_file.write_text(
        f"---\ntask_id: {task_id}\nassigned_agent: debug_worker\nstatus: todo\n"
        f"priority: normal\npod: stock_research_pod\ntask_type: {task_type}\n---\n\n"
        f"# {title}\n\n## Goal\n{body}\n",
        encoding="utf-8",
    )


def scan_and_process() -> None:
    if not BRIDGE_DIR.exists():
        return
    processed = _load_processed()
    for f in sorted(BRIDGE_DIR.glob("*.json")):
        if f.name not in processed:
            process_bridge_file(f)
            processed.add(f.name)
    _save_processed(processed)
```

- [ ] **Step 5: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_tony_bridge.py -v
```

Expected: 3 PASSED

- [ ] **Step 6: Add bridge scan to runner main.py**

Add at the start of `run_cycle()` in `runner/main.py`, after the budget check:

```python
    # Import at top of main.py:
    from runner.bridge.tony_bridge import scan_and_process as scan_tony_bridge

    # In run_cycle(), after budget check:
    scan_tony_bridge()
```

- [ ] **Step 7: Commit**

```powershell
git add runner\bridge\ bridge\ tests\runner\test_tony_bridge.py runner\main.py
git commit -m "feat: add Tony Stocks file bridge and scan integration"
```

---

## Task 9: Windows Task Scheduler Setup

**Files:**
- Create: `runner/scheduler/__init__.py`
- Create: `runner/scheduler/setup_windows.py`

- [ ] **Step 1: Create directory**

```powershell
New-Item -ItemType Directory -Force runner\scheduler
"" | Out-File runner\scheduler\__init__.py -Encoding utf8
```

- [ ] **Step 2: Write `runner/scheduler/setup_windows.py`**

```python
# runner/scheduler/setup_windows.py
"""
One-time setup: registers 4 scheduled tasks in Windows Task Scheduler.
Run once as administrator: python -m runner.scheduler.setup_windows
"""
import subprocess
import sys
from pathlib import Path

PYTHON = sys.executable
RUNNER_SCRIPT = str(Path(__file__).parent.parent.parent / "scripts" / "run_cycle.py")

SCHEDULES = [
    {
        "name": "AIops_DailyHealthCheck",
        "schedule": "/SC DAILY /ST 09:00",
        "description": "Atlas daily health check — 9am",
    },
    {
        "name": "AIops_HourlyQueueScan",
        "schedule": "/SC HOURLY /MO 1",
        "description": "Scout hourly queue scan",
    },
    {
        "name": "AIops_NightlyReport",
        "schedule": "/SC DAILY /ST 22:00",
        "description": "Ledger nightly report — 10pm",
    },
    {
        "name": "AIops_WeeklyEvaluation",
        "schedule": "/SC WEEKLY /D FRI /ST 15:00",
        "description": "Atlas weekly model evaluation — Friday 3pm",
    },
]


def register_task(name: str, schedule: str, description: str) -> bool:
    cmd = (
        f'schtasks /Create /TN "{name}" /TR "{PYTHON} {RUNNER_SCRIPT}" '
        f'{schedule} /F /RL HIGHEST /RU SYSTEM'
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  [OK] {name} — {description}")
        return True
    else:
        print(f"  [FAIL] {name}: {result.stderr.strip()}")
        return False


def setup_all() -> None:
    print("Registering AI Ops scheduled tasks in Windows Task Scheduler...")
    for s in SCHEDULES:
        register_task(s["name"], s["schedule"], s["description"])
    print("Done. View tasks with: schtasks /Query /FO LIST /TN AIops*")


if __name__ == "__main__":
    setup_all()
```

- [ ] **Step 3: Create `scripts/run_cycle.py`**

```python
# scripts/run_cycle.py
"""Entry point for scheduled runner invocations."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from runner.main import run_cycle
run_cycle()
```

- [ ] **Step 4: Run the scheduler setup (requires Administrator)**

Open PowerShell as Administrator, then:
```powershell
python -m runner.scheduler.setup_windows
```

Expected output:
```
Registering AI Ops scheduled tasks in Windows Task Scheduler...
  [OK] AIops_DailyHealthCheck — Atlas daily health check — 9am
  [OK] AIops_HourlyQueueScan — Scout hourly queue scan
  [OK] AIops_NightlyReport — Ledger nightly report — 10pm
  [OK] AIops_WeeklyEvaluation — Atlas weekly model evaluation — Friday 3pm
Done. View tasks with: schtasks /Query /FO LIST /TN AIops*
```

- [ ] **Step 5: Verify tasks registered**

```powershell
schtasks /Query /FO LIST /TN AIops_DailyHealthCheck
```

Expected: Shows task name, status Ready, next run time.

- [ ] **Step 6: Run full test suite one final time**

```powershell
python -m pytest tests/ -v --tb=short
```

Expected: All PASSED.

- [ ] **Step 7: Final commit**

```powershell
git add runner\scheduler\ scripts\run_cycle.py
git commit -m "feat: add Windows Task Scheduler setup — Plan 3 complete"
```

---

## Full System Launch

With all three plans complete, start everything:

```powershell
# Set API keys
$env:ANTHROPIC_API_KEY = "your-anthropic-key"
$env:OPENAI_API_KEY = "your-openai-key"  # for image + audio tools

# Terminal 1 — Dashboard
python scripts/start_dashboard.py
# Open http://127.0.0.1:8765

# Terminal 2 — Run one cycle manually to test
python scripts/run_cycle.py

# Windows Task Scheduler handles recurring runs automatically.
# To trigger manually at any time:
python scripts/run_cycle.py
```

Agents are now live. The dashboard updates in real time as agents pick tasks, execute, and complete.
