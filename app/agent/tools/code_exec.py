"""Sandboxed Python code execution.

Runs untrusted Python in a per-run temporary directory with
resource limits and a timeout. The sandbox uses the backend's
own interpreter (``sys.executable``) so packages installed in
the backend venv (e.g. plotly) are available, but:

- the working directory is the sandbox dir (relative writes
  stay contained),
- CPU time, address space, and file size are capped via
  ``setrlimit`` in the child,
- the environment is stripped to ``PATH``/``HOME`` only,
- execution is bounded by a wall-clock timeout.

This is a local-development sandbox. For production, run the
sandbox inside a container or VM (seccomp/landlock, no network).
"""
import asyncio
import os
import resource
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

DEFAULT_TIMEOUT_SECONDS = 30
MAX_MEMORY_BYTES = 512 * 1024 * 1024  # 512 MB
MAX_FILE_BYTES = 64 * 1024 * 1024     # 64 MB per file
MAX_CPU_SECONDS = 60
SANDBOX_ROOT = Path(tempfile.gettempdir()) / "agent_sandbox"
SANDBOX_TTL_SECONDS = 60 * 60  # prune sandboxes older than 1 hour


class SandboxError(Exception):
    """Raised when the sandbox cannot be started or is misconfigured."""


def _sandbox_dir(run_id: Optional[str]) -> Path:
    safe = str(run_id or "").replace("/", "_").replace("..", "_") or str(uuid.uuid4())
    d = SANDBOX_ROOT / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def _limit_resources():
    """Apply CPU/memory/file-size limits inside the child process."""
    try:
        resource.setrlimit(
            resource.RLIMIT_CPU,
            (MAX_CPU_SECONDS, MAX_CPU_SECONDS),
        )
        resource.setrlimit(
            resource.RLIMIT_AS,
            (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES),
        )
        resource.setrlimit(
            resource.RLIMIT_FSIZE,
            (MAX_FILE_BYTES, MAX_FILE_BYTES),
        )
    except (ValueError, OSError):
        # Limits are best-effort; if the platform rejects them we
        # still have the wall-clock timeout as a backstop.
        pass


def prune_sandboxes(now: Optional[float] = None) -> int:
    """Delete sandbox directories older than SANDBOX_TTL_SECONDS."""
    now = now if now is not None else time.time()
    removed = 0
    if not SANDBOX_ROOT.exists():
        return removed
    for child in SANDBOX_ROOT.iterdir():
        if not child.is_dir():
            continue
        try:
            if child.stat().st_mtime < now - SANDBOX_TTL_SECONDS:
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed


async def execute_python(
    code: str,
    run_id: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Execute ``code`` in an isolated temporary directory.

    Returns a dict with ``success``, ``stdout``, ``stderr``,
    ``returncode``, and ``artifacts`` (files created in the
    sandbox other than the entrypoint script).
    """
    prune_sandboxes()
    sandbox = _sandbox_dir(run_id)
    code_path = sandbox / "main.py"
    code_path.write_text(code)

    # Minimal environment: no secrets, no proxy vars, no PATH beyond
    # the system one. The child runs with the sandbox as cwd so any
    # relative file writes land inside it.
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(sandbox),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",  # isolated mode: ignore user site-packages & env vars
            str(code_path),
            cwd=str(sandbox),
            env=env,
            preexec_fn=_limit_resources,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as exc:
        raise SandboxError(f"failed to start sandbox: {exc}")

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {
            "success": False,
            "error": f"execution timed out after {timeout}s",
            "stdout": "",
            "stderr": "",
            "returncode": None,
            "artifacts": [],
        }

    artifacts = [
        {"name": p.name, "size": p.stat().st_size}
        for p in sorted(sandbox.iterdir())
        if p.is_file() and p.name != "main.py"
    ]
    return {
        "success": proc.returncode == 0,
        "stdout": stdout.decode("utf-8", "replace"),
        "stderr": stderr.decode("utf-8", "replace"),
        "returncode": proc.returncode,
        "artifacts": artifacts,
        "sandbox_dir": str(sandbox),
    }
