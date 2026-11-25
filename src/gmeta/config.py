"""Runtime configuration: data dirs and pixi-aware binary resolution.

Mirrors gside's config module (env prefix ``GMETA_``) with one deliberate
difference: gmeta's databases are tens-of-GB external downloads, so the
default DB dir is never inside the package — a repo checkout uses
``<repo>/data/db`` (gitignored), an installed package falls back to the
XDG data home. The bundled small data (Chinese name tables, pathogen lists)
ships inside the package and is resolved by the report modules directly.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent


def _default_db_dir(package_root: Path, project_root: Path) -> Path:
    """Databases are large external downloads — never inside the package or repo.

    Default: the XDG data home (``$XDG_DATA_HOME/gmeta/db``, falling back to
    ``~/.local/share/gmeta/db``). Override with ``GMETA_DB_DIR`` — the
    recommended setup for servers, where databases usually live on a data
    volume.
    """
    xdg = os.environ.get("XDG_DATA_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "gmeta" / "db"


def resolve_db_dir() -> Path:
    """DB root: ``$GMETA_DB_DIR`` wins, then the location-aware default."""
    return Path(os.environ.get("GMETA_DB_DIR", "") or _default_db_dir(PACKAGE_ROOT, PROJECT_ROOT))


DB_DIR = resolve_db_dir()

# Search order: GMETA_PIXI_BIN, the repo's own pixi env, the user-level pixi
# env, then PATH. Machine-specific tool dirs belong in GMETA_PIXI_BIN.
_KNOWN_PIXI_ROOTS = (
    PROJECT_ROOT / ".pixi/envs/default/bin",
    Path.home() / ".pixi/envs/default/bin",
)


def pixi_path() -> str:
    candidates = [os.environ.get("GMETA_PIXI_BIN", "")]
    candidates += [str(p) for p in _KNOWN_PIXI_ROOTS if p.exists()]
    prefix = ":".join(c for c in candidates if c)
    return f"{prefix}:{os.environ.get('PATH', '')}"


def which(tool: str) -> str | None:
    return shutil.which(tool, path=pixi_path())
