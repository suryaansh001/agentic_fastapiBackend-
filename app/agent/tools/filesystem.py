"""Sandboxed filesystem access for agent tools.

All file operations are contained within AGENT_WORKSPACE_ROOT. Absolute paths,
parent traversal (../), and escapes outside the root are rejected. Application
source, secrets and configuration are never reachable from agent tools.
"""
import os
from pathlib import Path
from typing import Optional

from app.config.settings import settings


class WorkspaceError(Exception):
    pass


def workspace_root() -> Path:
    return Path(settings.AGENT_WORKSPACE_ROOT).expanduser().resolve()


def resolve_workspace_path(path: str) -> Path:
    """Resolve a tool-supplied path inside the workspace root.

    Rejects:
    - absolute paths outside the workspace
    - any traversal that escapes the workspace (../, symlinked escapes)
    - the workspace root itself for write operations (handled by callers)
    """
    if not path or not isinstance(path, str):
        raise WorkspaceError("path is required")
    root = workspace_root()
    raw = Path(path).expanduser()
    if raw.is_absolute():
        candidate = raw.resolve()
    else:
        candidate = (root / raw).resolve()
    if candidate == root or root not in candidate.parents:
        raise WorkspaceError(
            f"path escapes the agent workspace: {path}"
        )
    return candidate


def ensure_parent(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise WorkspaceError(f"cannot create directory: {e}")


def read_text_file(path: str, max_bytes: int = 1_000_000) -> str:
    candidate = resolve_workspace_path(path)
    if not candidate.is_file():
        raise WorkspaceError(f"not a file: {path}")
    try:
        size = candidate.stat().st_size
    except OSError as e:
        raise WorkspaceError(f"cannot stat file: {e}")
    if size > max_bytes:
        raise WorkspaceError(f"file too large: {size} bytes (max {max_bytes})")
    try:
        return candidate.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise WorkspaceError(f"cannot read file: {e}")


def write_text_file(path: str, content: str, max_bytes: int = 1_000_000) -> str:
    candidate = resolve_workspace_path(path)
    if len(content.encode("utf-8")) > max_bytes:
        raise WorkspaceError(f"content too large (max {max_bytes} bytes)")
    ensure_parent(candidate)
    try:
        candidate.write_text(content, encoding="utf-8")
    except OSError as e:
        raise WorkspaceError(f"cannot write file: {e}")
    return str(candidate)


def list_workspace(pattern: str = "**/*", base: Optional[str] = None) -> list:
    import glob as _glob
    root = workspace_root()
    base_path = resolve_workspace_path(base) if base else root
    search_root = base_path if base_path.is_dir() else base_path.parent
    results = _glob.glob(str(search_root / pattern), recursive=True)
    return [os.path.relpath(r, root) for r in results if root in Path(r).resolve().parents or Path(r).resolve() == root]


def grep_workspace(pattern: str, path: Optional[str] = None) -> list:
    """Search file contents inside the workspace only."""
    import subprocess
    root = workspace_root()
    search_dir = root
    if path:
        base = resolve_workspace_path(path)
        search_dir = base if base.is_dir() else base.parent
    try:
        result = subprocess.run(
            ["grep", "-r", "-I", "--", pattern, str(search_dir)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return [line for line in result.stdout.splitlines()]
    except (subprocess.TimeoutExpired, OSError) as e:
        raise WorkspaceError(f"grep failed: {e}")
