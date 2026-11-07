"""Kraken2 + Bracken metagenomic profiling.

Parser half ported from gside's ``kraken2_identifier`` and extended: gmeta
parses the full kreport tree (every rank, not just R/U totals) because
surveillance reports need genus-level context around the species calls.
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from gmeta.analysis._envelope import METAGENOMIC, MethodEnvelope
from gmeta.config import DB_DIR, which
from gmeta.engine._env import require_bin, run_checked

_K2_HINT = "kraken2 not found — pixi add kraken2 bracken"
_BRACKEN_HINT = "bracken not found — pixi add kraken2 bracken"

_HIGH_FRACTION = 0.10
_MEDIUM_FRACTION = 0.01
_TOP_N = 20

# kraken-style rank code → report-friendly rank name.
_RANK_CODES = {
    "D": "domain",
    "K": "kingdom",
    "P": "phylum",
    "C": "class",
    "O": "order",
    "F": "family",
    "G": "genus",
    "S": "species",
}


@dataclass
class Kraken2Result(MethodEnvelope):
    analysis_type: ClassVar[str] = METAGENOMIC
    method: str = "kraken2_bracken"


@dataclass
class KreportRow:
    """One non-empty kreport line at any rank.

    ``depth`` is the name column's indentation (spaces), 0 for root; it is
    what makes the report a tree — children are always more indented than
    their parent (kraken2 uses 2 spaces per level).
    """

    fraction: float
    reads: int  # reads assigned at this rank directly
    reads_total: int  # reads assigned at this rank or below
    rank: str  # spelled-out rank ("species", "genus", ...)
    taxid: int
    name: str
    depth: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "fraction": self.fraction,
            "reads": self.reads,
            "reads_total": self.reads_total,
            "rank": self.rank,
            "taxid": self.taxid,
            "name": self.name,
            "depth": self.depth,
        }


@dataclass
class KreportSummary:
    total_reads: int = 0
    classified_reads: int = 0
    unclassified_reads: int = 0
    rows: list[KreportRow] = field(default_factory=list)

    @property
    def classified_fraction(self) -> float:
        return self.classified_reads / self.total_reads if self.total_reads else 0.0

    def at_rank(self, rank: str) -> list[KreportRow]:
        """Rows of one spelled-out rank, sorted by reads_total descending."""
        matching = [row for row in self.rows if row.rank == rank]
        matching.sort(key=lambda r: r.reads_total, reverse=True)
        return matching

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_reads": self.total_reads,
            "classified_reads": self.classified_reads,
            "unclassified_reads": self.unclassified_reads,
            "classified_fraction": round(self.classified_fraction, 6),
            "rows": [row.to_dict() for row in self.rows],
        }


def _fraction_confidence(fraction: float) -> str:
    if fraction >= _HIGH_FRACTION:
        return "high"
    if fraction >= _MEDIUM_FRACTION:
        return "medium"
    return "low"


def _parse_line(line: str) -> tuple[str, str, str, str, str, str] | None:
    """One kreport line → (fraction, clade_reads, direct_reads, code, taxid, raw_name).

    kraken2 column order: percent | reads at clade (children included) |
    reads assigned directly | rank code | taxid | indented name.
    ``raw_name`` keeps its leading indentation — that indentation is the tree
    structure (children are more indented than their parent).
    Handles the three shapes seen in the wild: tab-separated with taxid (the
    kraken2 default), tab-separated without taxid, and space-aligned reports
    (some re-implementations). Returns None for anything else.
    """
    cols = line.rstrip("\n").split("\t")
    if len(cols) >= 6:
        return cols[0], cols[1], cols[2], cols[3], cols[4], cols[5].rstrip()
    if len(cols) == 5:
        fraction, clade, direct, code, name = cols
        return fraction, clade, direct, code, "0", name.rstrip()
    parts = line.split()
    if len(parts) >= 6:
        return parts[0], parts[1], parts[2], parts[3], parts[4], " ".join(parts[5:])
    if len(parts) == 5:
        fraction, clade, direct, code, name = parts
        return fraction, clade, direct, code, "0", name
    return None


def parse_kreport(path: str | Path) -> KreportSummary:
    """Full kreport parse: R/U totals plus one row per classified clade.

    Sub-species codes (``S1``…) and unranked entries are kept with their raw
    code as rank so no information is silently dropped.
    """
    summary = KreportSummary()
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        parsed = _parse_line(line)
        if parsed is None:
            continue
        fraction, clade_reads, direct_reads, code, taxid, name = parsed
        if code == "R":
            summary.classified_reads = int(clade_reads)
            continue
        if code == "U":
            summary.unclassified_reads = int(clade_reads)
            continue
        try:
            depth = len(name) - len(name.lstrip(" "))
            row = KreportRow(
                fraction=float(fraction) / 100.0,
                reads=int(direct_reads),
                reads_total=int(clade_reads),
                rank=_RANK_CODES.get(code, code),
                taxid=int(taxid),
                name=name.strip(" "),
                depth=depth,
            )
        except ValueError:
            continue
        summary.rows.append(row)
    summary.total_reads = summary.classified_reads + summary.unclassified_reads
    return summary


def parse_bracken(path: str | Path) -> list[dict[str, Any]]:
    """Species rows of a bracken report, sorted by fraction descending.

    ``fraction_total_reads`` is a percentage (values sum to ~100); rows are
    normalised to 0..1 fractions. Hand-written reports that already use 0..1
    are detected via the column sum and passed through unchanged.

    bracken emits kraken-style rank codes ("S" for species); the spelled-out
    "species" is accepted too so hand-written reports keep parsing.
    """
    species: list[dict[str, Any]] = []
    lines = Path(path).read_text().splitlines()
    raw_fractions: list[float] = []
    parsed: list[tuple[str, int, int, float]] = []
    for line in lines[1:]:
        cols = line.split("\t")
        if len(cols) < 7:
            continue
        name, taxid, lvl, _assigned, _added, new_est, fraction = cols[:7]
        if lvl not in ("S", "species"):
            continue
        try:
            taxid = int(taxid)
            reads = int(new_est)
            frac = float(fraction)
        except ValueError:
            continue
        parsed.append((name.strip(), taxid, reads, frac))
        raw_fractions.append(frac)

    # Percentage-scale if the column sums to ~100 (a true 0..1 column sums to ≤1).
    percent_scale = sum(raw_fractions) > 1.5 if raw_fractions else False
    for name, taxid, reads, frac in parsed:
        fraction = frac / 100.0 if percent_scale else frac
        species.append(
            {
                "name": name,
                "taxid": taxid,
                "reads": reads,
                "fraction": fraction,
                "confidence": _fraction_confidence(fraction),
            }
        )
    species.sort(key=lambda s: s["fraction"], reverse=True)
    return species


def resolve_kraken2_db(db_dir: str | Path | None = None) -> Path:
    """Validate a kraken2 database directory (``*.k2d`` + bracken kmer distrib)."""
    db = Path(db_dir) if db_dir else DB_DIR / "kraken2"
    if not any(db.glob("*.k2d")):
        raise RuntimeError(
            f"Kraken2 database not found in {db} (run: gmeta db fetch kraken2, or set -D/--db-dir)"
        )
    distrib = sorted(db.glob("database*mers.kmer_distrib"))
    if not distrib:
        raise RuntimeError(
            f"Bracken kmer distribution not found in {db} (expected databaseXXXmers.kmer_distrib)"
        )
    return db


def _bracken_read_len(db: Path) -> str:
    """Read length encoded in the database's kmer_distrib file name."""
    distrib = sorted(db.glob("database*mers.kmer_distrib"))[0]
    stem = distrib.name  # database150mers.kmer_distrib
    digits = "".join(ch for ch in stem if ch.isdigit())
    return digits or "150"


def run_kraken2(
    db: Path,
    inputs: Sequence[str | Path],
    threads: int,
    work: Path,
) -> Path:
    """Classify reads; returns the kreport path (paired when two inputs)."""
    k2_bin = require_bin("kraken2", hint=_K2_HINT, resolver=which)
    kreport = work / "kreport.txt"
    cmd = [
        k2_bin,
        "--db",
        str(db),
        "--threads",
        str(threads),
        "--output",
        str(work / "kraken.out"),
        "--report",
        str(kreport),
    ]
    if len(inputs) == 2:
        cmd.append("--paired")
    cmd += [str(f) for f in inputs]
    run_checked(cmd, timeout=3600, name="kraken2 failed")
    return kreport


def run_bracken(db: Path, kreport: Path, work: Path, threshold: int = 10) -> Path:
    """Re-estimate species abundances; returns the bracken report path."""
    bracken_bin = require_bin("bracken", hint=_BRACKEN_HINT, resolver=which)
    bracken_out = work / "bracken.txt"
    run_checked(
        [
            bracken_bin,
            "-d",
            str(db),
            "-i",
            str(kreport),
            "-o",
            str(bracken_out),
            "-r",
            _bracken_read_len(db),
            "-t",
            str(threshold),
        ],
        timeout=300,
        name="bracken failed",
    )
    return bracken_out


def profile_kraken2(
    files: Sequence[str | Path],
    db_dir: str | Path | None = None,
    threads: int = 4,
    work_dir: str | Path | None = None,
) -> Kraken2Result:
    """Profile one sample with kraken2 + bracken (1 file = single-end, 2 = paired)."""
    db = resolve_kraken2_db(db_dir)
    inputs = [str(f) for f in files]

    if work_dir is not None:
        work = Path(work_dir)
        work.mkdir(parents=True, exist_ok=True)
        kreport = run_kraken2(db, inputs, threads, work)
        bracken_out = run_bracken(db, kreport, work)
        summary = parse_kreport(kreport)
        species = parse_bracken(bracken_out)
    else:
        with tempfile.TemporaryDirectory(prefix="gmeta-kraken2-") as tmp:
            work = Path(tmp)
            kreport = run_kraken2(db, inputs, threads, work)
            bracken_out = run_bracken(db, kreport, work)
            summary = parse_kreport(kreport)
            species = parse_bracken(bracken_out)

    return Kraken2Result(
        database={"name": db.name, "path": str(db)},
        result={
            "top_species": species[:_TOP_N],
            "total_reads": summary.total_reads,
            "classified_reads": summary.classified_reads,
            "classified_fraction": round(summary.classified_fraction, 6),
            "n_species": len(species),
        },
    )
