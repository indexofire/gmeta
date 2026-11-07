"""MetaPhlAn profiling: marker-gene relative abundance with read estimates.

Runs ``metaphlan -t rel_ab_w_read_stats`` so the profile carries estimated
read counts; the parser consumes both that layout and plain ``rel_ab``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from gmeta.analysis._envelope import METAGENOMIC, MethodEnvelope
from gmeta.analysis.profilers import parse_metaphlan_profile
from gmeta.config import DB_DIR, which
from gmeta.engine._env import require_bin, run_checked

_METAPHLAN_HINT = "metaphlan not found — pixi add metaphlan"

_TOP_N = 20


@dataclass
class MetaphlanResult(MethodEnvelope):
    analysis_type: ClassVar[str] = METAGENOMIC
    method: str = "metaphlan"


def resolve_metaphlan_db(db_dir: str | Path | None = None) -> Path:
    """MetaPhlAn bowtie2 database directory (``mpa_v*/`` index files)."""
    db = Path(db_dir) if db_dir else DB_DIR / "metaphlan"
    if db.is_dir() and (list(db.glob("mpa_v*")) or list(db.glob("*.bt2l*"))):
        return db
    raise RuntimeError(
        f"metaphlan database not found in {db} (run: gmeta db fetch metaphlan, or set -D/--db-dir)"
    )


def run_metaphlan(
    inputs: Sequence[str | Path],
    db_dir: Path,
    threads: int,
    work: Path,
) -> Path:
    """Profile reads → ``work/profile.tsv`` (rel_ab_w_read_stats layout)."""
    metaphlan = require_bin("metaphlan", hint=_METAPHLAN_HINT, resolver=which)
    profile = work / "profile.tsv"
    cmd = [
        metaphlan,
        ",".join(str(i) for i in inputs),
        "--input_type",
        "fastq",
        "-t",
        "rel_ab_w_read_stats",
        "--nproc",
        str(threads),
        "--bowtie2db",
        str(db_dir),
        "-o",
        str(profile),
    ]
    bowtie2_out = work / "metagenome.bowtie2.bz2"
    cmd += ["--bowtie2out", str(bowtie2_out)]
    run_checked(cmd, timeout=14400, name="metaphlan failed")
    return profile


def profile_metaphlan(
    files: Sequence[str | Path],
    db_dir: str | Path | None = None,
    threads: int = 4,
    work_dir: str | Path | None = None,
) -> MetaphlanResult:
    """Profile one sample with MetaPhlAn (1 file = single-end, 2 = paired)."""
    import contextlib
    import tempfile

    db = resolve_metaphlan_db(db_dir)

    if work_dir is not None:
        work = Path(work_dir)
        work.mkdir(parents=True, exist_ok=True)
        ctx = contextlib.nullcontext(work)  # type: ignore[arg-type]
    else:
        ctx = tempfile.TemporaryDirectory(prefix="gmeta-metaphlan-")  # type: ignore[assignment]
    with ctx as tmp:
        work = Path(tmp)
        profile_path = run_metaphlan(files, db, threads, work)
        profile = parse_metaphlan_profile(profile_path)

    return MetaphlanResult(
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
