"""Single home for binary discovery + checked subprocess execution.

Ported from gside's ``engine/_env.py``: one resolver, one checked runner,
identical error wording across the tool family.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from ..config import which

__all__ = ["require_bin", "run_checked", "run_to_file", "which"]


def require_bin(
    tool: str,
    *,
    hint: str = "",
    resolver: Callable[[str], str | None] | None = None,
) -> str:
    """Resolve ``tool`` to a path or raise RuntimeError with ``hint`` as the message.

    Callers pass this module's ``which`` as ``resolver`` so tests can
    monkeypatch the lookup without touching ``shutil``.
    """
    found = (resolver or which)(tool)
    if not found:
        raise RuntimeError(hint or f"{tool} not found in PATH")
    return found


def run_checked(
    cmd: list[str],
    *,
    timeout: int,
    name: str,
    exit_in_msg: bool = True,
    truncate: int | None = 500,
) -> subprocess.CompletedProcess[str]:
    """Run ``cmd`` captured; on nonzero exit raise RuntimeError as
    ``"{name}{' (exit N)' if exit_in_msg}: {stderr.strip()[:truncate]}"``.
    """
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        detail = proc.stderr.strip()
        if truncate is not None:
            detail = detail[:truncate]
        exit_part = f" (exit {proc.returncode})" if exit_in_msg else ""
        raise RuntimeError(f"{name}{exit_part}: {detail}")
    return proc


def run_to_file(
    cmd: list[str],
    *,
    stdout_path: str | Path,
    timeout: int,
    name: str,
) -> Path:
    """Run ``cmd`` with stdout streamed to ``stdout_path`` (tools like
    centrifuge write results to stdout; capturing in memory would balloon)."""
    out = Path(stdout_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, timeout=timeout)
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="ignore").strip()[:500]
        raise RuntimeError(f"{name} (exit {proc.returncode}): {detail}")
    return out
