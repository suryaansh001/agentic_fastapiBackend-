"""Tests for sandboxed Python execution and Plotly chart generation."""
import asyncio
import os
import tempfile

import pytest

from app.agent.tools.charts import ChartError, create_chart
from app.agent.tools.code_exec import (
    SandboxError,
    execute_python,
    prune_sandboxes,
)
from app.agent.tools.registry import (
    RISK_APPROVAL_REQUIRED,
    ToolContext,
    default_registry,
)


# --- sandboxed python execution -------------------------------------


@pytest.mark.asyncio
async def test_execute_python_runs_code():
    result = await execute_python(
        'print("hello")\nprint(2 + 2)', run_id="test-exec-1"
    )
    assert result["success"] is True
    assert "hello" in result["stdout"]
    assert "4" in result["stdout"]
    assert result["returncode"] == 0


@pytest.mark.asyncio
async def test_execute_python_captures_stderr():
    result = await execute_python(
        'import sys; sys.stderr.write("boom")',
        run_id="test-exec-2",
    )
    assert result["success"] is True
    assert "boom" in result["stderr"]


@pytest.mark.asyncio
async def test_execute_python_nonzero_exit():
    result = await execute_python(
        'raise SystemExit(3)', run_id="test-exec-3"
    )
    assert result["success"] is False
    assert result["returncode"] == 3


@pytest.mark.asyncio
async def test_execute_python_timeout():
    result = await execute_python(
        "import time; time.sleep(10)",
        run_id="test-exec-4",
        timeout=2,
    )
    assert result["success"] is False
    assert "timed out" in result["error"]


@pytest.mark.asyncio
async def test_execute_python_artifacts():
    result = await execute_python(
        'open("out.txt", "w").write("data")',
        run_id="test-exec-5",
    )
    assert result["success"] is True
    names = [a["name"] for a in result["artifacts"]]
    assert "out.txt" in names


@pytest.mark.asyncio
async def test_execute_python_writes_confined_to_sandbox():
    # A relative write must land inside the sandbox dir.
    result = await execute_python(
        'open("rel.txt", "w").write("x")',
        run_id="test-exec-6",
    )
    assert result["success"] is True
    sandbox_dir = result["sandbox_dir"]
    assert os.path.exists(os.path.join(sandbox_dir, "rel.txt"))


def test_prune_sandboxes_removes_old(tmp_path, monkeypatch):
    old = tmp_path / "old_sandbox"
    old.mkdir()
    # Backdate the directory's mtime.
    old_time = os.stat(old).st_mtime - 10_000
    os.utime(old, (old_time, old_time))
    new = tmp_path / "new_sandbox"
    new.mkdir()
    monkeypatch.setattr(
        "app.agent.tools.code_exec.SANDBOX_ROOT", tmp_path
    )
    removed = prune_sandboxes()
    assert removed == 1
    assert not old.exists()
    assert new.exists()


# --- plotly chart generation ----------------------------------------


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.agent.tools.charts.settings.AGENT_WORKSPACE_ROOT",
        str(tmp_path),
    )
    return tmp_path


def test_create_chart_bar_writes_html(workspace):
    result = create_chart(
        chart_type="bar",
        x=["A", "B", "C"],
        y=[1, 2, 3],
        title="Test",
        filename="bar_chart",
    )
    assert result["written"] is True
    assert result["points"] == 3
    assert result["path"].endswith("bar_chart.html")
    assert os.path.exists(result["path"])


def test_create_chart_donut_with_png(workspace):
    result = create_chart(
        chart_type="donut",
        x=["X", "Y"],
        y=[1, 2],
        filename="donut_chart",
        as_png=True,
    )
    assert os.path.exists(result["path"])
    assert "png_path" in result
    assert os.path.exists(result["png_path"])


def test_create_chart_invalid_type():
    with pytest.raises(ChartError):
        create_chart(chart_type="bogus", x=[1], y=[1])


def test_create_chart_length_mismatch():
    with pytest.raises(ChartError):
        create_chart(chart_type="bar", x=[1, 2], y=[1])


def test_create_chart_empty():
    with pytest.raises(ChartError):
        create_chart(chart_type="bar", x=[], y=[])


# --- registry wiring -----------------------------------------------


def test_execute_python_and_chart_registered_as_approval_required():
    registry = default_registry()
    for name in ("execute_python", "create_chart"):
        spec = registry.get(name)
        assert spec is not None
        assert spec.risk == RISK_APPROVAL_REQUIRED


@pytest.mark.asyncio
async def test_execute_python_handler_returns_bounded_output():
    registry = default_registry()
    ctx = ToolContext(run_id="test-handler-1", user_id="user_1")
    result = await registry.execute(
        "execute_python",
        {"code": 'print("ok")'},
        ctx,
    )
    assert result["success"] is True
    assert "ok" in result["stdout"]


@pytest.mark.asyncio
async def test_create_chart_handler(workspace):
    registry = default_registry()
    ctx = ToolContext(run_id="test-handler-2", user_id="user_1")
    result = await registry.execute(
        "create_chart",
        {
            "chartType": "bar",
            "x": ["A", "B"],
            "y": [1, 2],
            "filename": "handler_chart",
        },
        ctx,
    )
    assert result["success"] is True
    assert result["written"] is True
    assert os.path.exists(result["path"])


@pytest.mark.asyncio
async def test_create_chart_handler_invalid():
    registry = default_registry()
    ctx = ToolContext(run_id="test-handler-3", user_id="user_1")
    result = await registry.execute(
        "create_chart",
        {"chartType": "bogus", "x": [1], "y": [1]},
        ctx,
    )
    assert result["success"] is False
    assert "error" in result
