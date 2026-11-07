"""Kaiju profiling: protein-level classification + kaiju2table summaries.

kaiju2table runs per rank, so one species table and one genus table are
generated — real genus counts for the 识别网 export instead of aggregation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from gmeta.analysis._envelope import METAGENOMIC, MethodEnvelope
from gmeta.analysis.profilers import attach_kaiju_genus, parse_kaiju_table
from gmeta.config import DB_DIR, which
from gmeta.engine._env import require_bin, run_checked

_KAIJU_HINT = "kaiju not found — pixi add kaiju"
_KAIJU2TABLE_HINT = "kaiju2table not found — pixi add kaiju"

_TOP_N = 20


@dataclass
class KaijuResult(MethodEnvelope):
    analysis_type: ClassVar[str] = METAGENOMIC
    method: str = "kaiju"


def resolve_kaiju_db(db_dir: str | Path | None = None) -> Path:
    """Kaiju database directory: needs ``nodes.dmp`` + ``*.fmi`` (+ names.dmp)."""
    db = Path(db_dir) if db_dir else DB_DIR / "kaiju"
    if not (db / "nodes.dmp").is_file() or not list(db.glob("*.fmi")):
        raise RuntimeError(
            f"kaiju database not found in {db} (needs nodes.dmp + *.fmi; "
            "run: gmeta db fetch kaiju, or set -D/--db-dir)"
        )
    if not (db / "names.dmp").is_file():
        raise RuntimeError(f"names.dmp missing in {db} (kaiju2table requires it)")
    return db


def run_kaiju(
    inputs: Sequence[str | Path],
    db_dir: Path,
    threads: int,
    work: Path,
) -> Path:
    """Classify reads at the protein level → ``work/kaiju.out``."""
    kaiju = require_bin("kaiju", hint=_KAIJU_HINT, resolver=which)
    fmi = sorted(db_dir.glob("*.fmi"))[0]
    cmd = [
        kaiju,
        "-t",
        str(db_dir / "nodes.dmp"),
        "-f",
        str(fmi),
        "-z",
        str(threads),
        "-o",
        str(work / "kaiju.out"),
    ]
    if len(inputs) == 2:
        cmd += ["-i", str(inputs[0]), "-j", str(inputs[1])]
    else:
        cmd += ["-i", str(inputs[0])]
    run_checked(cmd, timeout=7200, name="kaiju failed")
    return work / "kaiju.out"


def run_kaiju2table(
    kaiju_out: Path,
    db_dir: Path,
    rank: str,
    work: Path,
) -> Path:
    """Summarise at one rank → ``work/kaiju.<rank>.tsv``."""
    kaiju2table = require_bin("kaiju2table", hint=_KAIJU2TABLE_HINT, resolver=which)
    table = work / f"kaiju.{rank}.tsv"
    run_checked(
        [
            kaiju2table,
            "-t",
            str(db_dir / "nodes.dmp"),
            "-n",
            str(db_dir / "names.dmp"),
            "-r",
            rank,
            "-o",
            str(table),
            str(kaiju_out),
        ],
        timeout=600,
        name=f"kaiju2table ({rank}) failed",
    )
    return table


def profile_kaiju(
    files: Sequence[str | Path],
    db_dir: str | Path | None = None,
    threads: int = 4,
    work_dir: str | Path | None = None,
) -> KaijuResult:
    """Profile one sample with kaiju (1 file = single-end, 2 = paired)."""
    import contextlib
    import tempfile

    db = resolve_kaiju_db(db_dir)

    if work_dir is not None:
        work = Path(work_dir)
        work.mkdir(parents=True, exist_ok=True)
        ctx = contextlib.nullcontext(work)  # type: ignore[arg-type]
    else:
        ctx = tempfile.TemporaryDirectory(prefix="gmeta-kaiju-")  # type: ignore[assignment]
    with ctx as tmp:
        work = Path(tmp)
        kaiju_out = run_kaiju(files, db, threads, work)
        species_table = run_kaiju2table(kaiju_out, db, "species", work)
        genus_table = run_kaiju2table(kaiju_out, db, "genus", work)
        profile = attach_kaiju_genus(parse_kaiju_table(species_table), genus_table)

    return KaijuResult(
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
