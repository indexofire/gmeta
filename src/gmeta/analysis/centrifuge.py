"""Centrifuge profiling: classify reads, then convert to a kraken-style kreport.

``centrifuge-kreport`` emits the kraken2 report layout, so the existing
kreport parser (tree pairing, 识别网 export) applies unchanged — one honest
tree instead of a table approximation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from gmeta.analysis._envelope import METAGENOMIC, MethodEnvelope
from gmeta.analysis.kraken2 import KreportSummary, parse_kreport
from gmeta.config import DB_DIR, which
from gmeta.engine._env import require_bin, run_to_file

_CENTRIFUGE_HINT = "centrifuge not found — pixi add centrifuge"
_KREPORT_HINT = "centrifuge-kreport not found — pixi add centrifuge"

_TOP_N = 20


@dataclass
class CentrifugeResult(MethodEnvelope):
    analysis_type: ClassVar[str] = METAGENOMIC
    method: str = "centrifuge"


def resolve_centrifuge_db(db_dir: str | Path | None = None) -> str:
    """Centrifuge index prefix (files ``<prefix>.1.cf.index`` …) as a string.

    Accepts either the prefix itself or a directory containing index files.
    """
    candidate = Path(db_dir) if db_dir else DB_DIR / "centrifuge"
    if candidate.suffix == ".cf" or candidate.name.endswith(".cf.index"):
        return str(candidate)
    if candidate.is_dir():
        indexes = sorted(candidate.glob("*.1.cf.index*"))
        if indexes:
            # e.g. p_compressed.1.cf.index → prefix p_compressed
            return str(indexes[0]).split(".1.cf.index")[0]
        # a directory that IS the prefix (files named <dir>.1.cf.index beside it)
        sibling = sorted(candidate.parent.glob(f"{candidate.name}.1.cf.index*"))
        if sibling:
            return str(candidate)
    raise RuntimeError(
        f"centrifuge index not found at {candidate} "
        "(run: gmeta db fetch centrifuge, or set -D/--db-dir)"
    )


def run_centrifuge(
    inputs: Sequence[str | Path],
    db_prefix: str,
    threads: int,
    work: Path,
) -> Path:
    """Classify reads; classification TSV is streamed to ``work/centrifuge.tsv``."""
    centrifuge = require_bin("centrifuge", hint=_CENTRIFUGE_HINT, resolver=which)
    cmd = [centrifuge, "-x", db_prefix, "-p", str(threads), "-t"]
    if len(inputs) == 2:
        cmd += ["-1", str(inputs[0]), "-2", str(inputs[1])]
    else:
        cmd += ["-u", str(inputs[0])]
    return run_to_file(
        cmd, stdout_path=work / "centrifuge.tsv", timeout=7200, name="centrifuge failed"
    )


def run_centrifuge_kreport(db_prefix: str, classified_tsv: Path, work: Path) -> Path:
    """Convert the classification output to a kraken-style kreport."""
    kreport_bin = require_bin("centrifuge-kreport", hint=_KREPORT_HINT, resolver=which)
    return run_to_file(
        [kreport_bin, "-x", db_prefix, str(classified_tsv)],
        stdout_path=work / "kreport.txt",
        timeout=600,
        name="centrifuge-kreport failed",
    )


def profile_centrifuge(
    files: Sequence[str | Path],
    db_dir: str | Path | None = None,
    threads: int = 4,
    work_dir: str | Path | None = None,
) -> CentrifugeResult:
    """Classify one sample with centrifuge (1 file = single-end, 2 = paired).

    With ``work_dir`` the classification TSV and kreport are kept there (used
    by ``gmeta run`` so reports can cite them).
    """
    import contextlib
    import tempfile

    db_prefix = resolve_centrifuge_db(db_dir)

    if work_dir is not None:
        work = Path(work_dir)
        work.mkdir(parents=True, exist_ok=True)
        ctx = contextlib.nullcontext(work)  # type: ignore[arg-type]
    else:
        ctx = tempfile.TemporaryDirectory(prefix="gmeta-centrifuge-")  # type: ignore[assignment]
    with ctx as tmp:
        work = Path(tmp)
        classified = run_centrifuge(files, db_prefix, threads, work)
        kreport = run_centrifuge_kreport(db_prefix, classified, work)
        summary: KreportSummary = parse_kreport(kreport)
        species = [
            {
                "name": row.name,
                "taxid": row.taxid,
                "reads": row.reads_total,
                "fraction": row.fraction,
                "confidence": "low",
            }
            for row in summary.at_rank("species")
        ]

    return CentrifugeResult(
        database={"name": Path(db_prefix).name, "path": db_prefix},
        result={
            "top_species": species[:_TOP_N],
            "total_reads": summary.total_reads,
            "classified_reads": summary.classified_reads,
            "classified_fraction": round(summary.classified_fraction, 6),
            "n_species": len(species),
        },
    )
