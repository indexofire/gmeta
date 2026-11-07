"""KMCP profiling: k-mer search (single-end mode for sensitivity) + EM profiling.

Follows the official recipe: reads are searched as single-end files against
the index, then ``kmcp profile`` aggregates them per reference; gmeta's
parser groups the per-reference rows by taxid.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from gmeta.analysis._envelope import METAGENOMIC, MethodEnvelope
from gmeta.analysis.profilers import parse_kmcp_profile
from gmeta.config import DB_DIR, which
from gmeta.engine._env import require_bin, run_checked

_KMCP_HINT = "kmcp not found — pixi add kmcp"

_TOP_N = 20


@dataclass
class KmcpResult(MethodEnvelope):
    analysis_type: ClassVar[str] = METAGENOMIC
    method: str = "kmcp"


def resolve_kmcp_db(
    db_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    """(index dir with ``*.uniki`` + ``taxid.map``, NCBI taxdump dir)."""
    db = Path(db_dir) if db_dir else DB_DIR / "kmcp"
    if not db.is_dir() or not list(db.rglob("*.uniki")):
        raise RuntimeError(
            f"kmcp database not found in {db} (run: gmeta db fetch kmcp, or set -D/--db-dir)"
        )
    if not (db / "taxid.map").is_file() and not list(db.glob("*.map")):
        raise RuntimeError(f"taxid.map missing in {db} (kmcp profile requires it)")

    # sibling layout first ($DB_ROOT/kmcp + $DB_ROOT/taxdump), global default last
    candidates = [
        db / "taxdump",
        db.parent / "taxdump",
        DB_DIR / "taxdump",
    ]
    taxdump = next((c for c in candidates if (c / "nodes.dmp").is_file()), candidates[-1])
    if not (taxdump / "nodes.dmp").is_file():
        raise RuntimeError(
            f"NCBI taxdump (nodes.dmp/names.dmp) not found in {taxdump} "
            "(run: gmeta db fetch taxdump)"
        )
    return db, taxdump


def run_kmcp_search(
    inputs: Sequence[str | Path],
    db_dir: Path,
    threads: int,
    work: Path,
) -> Path:
    """Search reads (single-end mode for higher sensitivity) → search.tsv.gz."""
    kmcp = require_bin("kmcp", hint=_KMCP_HINT, resolver=which)
    out = work / "search.tsv.gz"
    run_checked(
        [
            kmcp,
            "search",
            "--threads",
            str(threads),
            "--db-dir",
            str(db_dir),
            "--min-kmers",
            "10",
            "--min-query-len",
            "30",
            "--min-query-cov",
            "0.55",
            *[str(i) for i in inputs],
            "--out-file",
            str(out),
        ],
        timeout=14400,
        name="kmcp search failed",
    )
    return out


def run_kmcp_profile(
    search_out: Path,
    db_dir: Path,
    taxdump: Path,
    work: Path,
) -> Path:
    """Aggregate search hits per reference → ``work/profile.tsv`` (17 columns)."""
    kmcp = require_bin("kmcp", hint=_KMCP_HINT, resolver=which)
    profile = work / "profile.tsv"
    taxid_map = db_dir / "taxid.map"
    if not taxid_map.is_file():
        taxid_map = sorted(db_dir.glob("*.map"))[0]
    run_checked(
        [
            kmcp,
            "profile",
            "--taxid-map",
            str(taxid_map),
            "--taxdump",
            str(taxdump),
            "--level",
            "species",
            str(search_out),
            "--out-file",
            str(profile),
        ],
        timeout=7200,
        name="kmcp profile failed",
    )
    return profile


def profile_kmcp(
    files: Sequence[str | Path],
    db_dir: str | Path | None = None,
    threads: int = 4,
    work_dir: str | Path | None = None,
) -> KmcpResult:
    """Profile one sample with kmcp search + profile (any number of inputs)."""
    import contextlib
    import tempfile

    db, taxdump = resolve_kmcp_db(db_dir)

    if work_dir is not None:
        work = Path(work_dir)
        work.mkdir(parents=True, exist_ok=True)
        ctx = contextlib.nullcontext(work)  # type: ignore[arg-type]
    else:
        ctx = tempfile.TemporaryDirectory(prefix="gmeta-kmcp-")  # type: ignore[assignment]
    with ctx as tmp:
        work = Path(tmp)
        search_out = run_kmcp_search(files, db, threads, work)
        profile_path = run_kmcp_profile(search_out, db, taxdump, work)
        profile = parse_kmcp_profile(profile_path)

    return KmcpResult(
        database={"name": db.name, "path": str(db)},
        result={
            "top_species": [
                {
                    "name": taxon.name,
                    "taxid": taxon.taxid,
                    "reads": taxon.reads,
                    "fraction": taxon.fraction,
                }
                for taxon in profile.species_sorted()[:_TOP_N]
            ],
            "n_species": len(profile.species),
        },
    )
