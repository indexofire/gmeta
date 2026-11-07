"""Sylph ANI-based metagenomic profiling (FASTQ reads only).

Parser and subprocess recipe ported from gside's ``sylph_identifier``
(the legacy path — gmeta does not depend on the gseek bridge).
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from gmeta.analysis._envelope import METAGENOMIC, MethodEnvelope
from gmeta.config import DB_DIR, which
from gmeta.engine._env import require_bin, run_checked

_SYLPH_HINT = "sylph not found — pixi add sylph"
FASTA_INPUT_ERROR = "sylph requires FASTQ reads, not contigs — use kraken2 for FASTA input"

_FASTA_SUFFIXES = (".fna", ".fa", ".fasta")

# ANI thresholds mirrored from gside's _thresholds.ani_confidence.
_HIGH_ANI = 95.0
_MEDIUM_ANI = 90.0


@dataclass
class SylphResult(MethodEnvelope):
    analysis_type: ClassVar[str] = METAGENOMIC
    method: str = "sylph_ani"


def ani_confidence(ani: float) -> str:
    if ani >= _HIGH_ANI:
        return "high"
    if ani >= _MEDIUM_ANI:
        return "medium"
    return "low"


def _looks_like_fasta(files: Sequence[str]) -> bool:
    return any(Path(f).suffix in _FASTA_SUFFIXES for f in files)


def _species_from_genome_file(genome_file: str) -> str:
    """``Escherichia_coli.fna`` → ``Escherichia coli``; accessions kept verbatim."""
    stem = Path(genome_file).stem
    if stem.startswith("GCF_") or stem.startswith("GCA_"):
        return stem
    return stem.replace("_", " ")


def _load_taxa_map(db_dir: Path) -> dict[str, str]:
    """Load filename→species from metadata.tsv if present near the sylph DB."""
    for candidate in (db_dir / "metadata.tsv", db_dir.parent / "metadata.tsv"):
        if candidate.is_file():
            mapping: dict[str, str] = {}
            for ln in candidate.read_text().splitlines()[1:]:
                cols = ln.split("\t")
                if len(cols) >= 2:
                    full = cols[0].strip()
                    species = cols[1].strip()
                    mapping[full] = species
                    mapping[Path(full).stem] = species
            return mapping
    return {}


def _find_sketch(work: Path) -> Path:
    """Locate the read sketch sylph wrote (v0 emits ``.syldata``, v1 ``.sylsp``)."""
    candidates = sorted(work.rglob("*.sylsp")) + sorted(work.rglob("*.syldata"))
    if not candidates:
        raise RuntimeError("sylph sketch produced no .syldata/.sylsp output")
    return candidates[0]


def parse_profile(path: str | Path, taxa_map: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """sylph profile TSV → species rows sorted by taxonomic abundance descending.

    ``Taxonomic_abundance`` is a percentage (100 = whole community) and is
    normalised to a 0..1 fraction; the scale is inferred from the column sum
    so 0..1 inputs also work.
    """
    lines = [ln for ln in Path(path).read_text().splitlines() if ln.strip()]
    if len(lines) < 2:
        return []
    mapping = taxa_map or {}
    header = lines[0].split("\t")
    raw: list[tuple[str, float, float, float]] = []
    for line in lines[1:]:
        row = dict(zip(header, line.split("\t"), strict=False))
        try:
            ani = float(row.get("Adjusted_ANI", 0.0))
            abundance = float(row.get("Taxonomic_abundance", 0.0))
            coverage = float(row.get("Eff_cov", 0.0))
        except ValueError:
            continue
        raw_name = row.get("Genome_file", "")
        stem = Path(raw_name).stem
        name = mapping.get(raw_name, mapping.get(stem, _species_from_genome_file(raw_name)))
        raw.append((name, ani, abundance, coverage))

    percent_scale = sum(item[2] for item in raw) > 1.5 if raw else False
    species: list[dict[str, Any]] = []
    for name, ani, abundance, coverage in raw:
        fraction = abundance / 100.0 if percent_scale else abundance
        species.append(
            {
                "name": name,
                "ani": ani,
                "abundance": fraction,
                "coverage": coverage,
                "confidence": ani_confidence(ani),
            }
        )
    species.sort(key=lambda s: s["abundance"], reverse=True)
    return species


def resolve_sylph_db(db_dir: str | Path | None = None) -> Path:
    """Locate a sylph database file (``.syl2db`` preferred over ``.syldb``)."""
    base = Path(db_dir) if db_dir else DB_DIR / "sylph"
    if base.is_file():
        return base
    if base.is_dir():
        # .syl2db is the v1 two-stage format and is preferred by sylph itself.
        dbs = sorted(base.glob("*.syl2db")) + sorted(base.glob("*.syldb"))
        if dbs:
            return dbs[0]
    raise RuntimeError(
        f"sylph database not found in {base} (run: gmeta db fetch sylph, or set -D/--db-dir)"
    )


def profile_sylph(
    files: Sequence[str | Path],
    db_dir: str | Path | None = None,
    threads: int = 4,
    work_dir: str | Path | None = None,
) -> SylphResult:
    """Profile one FASTQ sample with sylph sketch + profile (1 file = single, 2 = paired).

    With ``work_dir`` the sketch/profile artifacts are kept there instead of a
    temporary directory (used by ``gmeta run`` so reports can cite them).
    """
    sylph_bin = require_bin("sylph", hint=_SYLPH_HINT, resolver=which)

    inputs = [str(f) for f in files]
    if _looks_like_fasta(inputs):
        raise RuntimeError(FASTA_INPUT_ERROR)

    db_file = resolve_sylph_db(db_dir)
    base = db_file.parent
    taxa_map = _load_taxa_map(base)

    import contextlib

    tmp_ctx = (
        contextlib.nullcontext(Path(work_dir))
        if work_dir
        else tempfile.TemporaryDirectory(  # noqa: SIM115
            prefix="gmeta-sylph-"
        )
    )
    with tmp_ctx as tmp:
        work = Path(tmp)
        work.mkdir(parents=True, exist_ok=True)
        # sylph v1: read sketches ignore -o (genomes only) — they go to a
        # folder given via -d; paired reads must ride the -1/-2 flags.
        sketch_dir = work / "sketches"
        sketch_cmd = [sylph_bin, "sketch", "-t", str(threads)]
        if len(inputs) == 2:
            sketch_cmd += ["-1", inputs[0], "-2", inputs[1]]
        else:
            sketch_cmd += inputs
        sketch_cmd += ["-d", str(sketch_dir)]
        run_checked(sketch_cmd, timeout=3600, name="sylph sketch failed")

        profile = work / "profile.tsv"
        run_checked(
            [
                sylph_bin,
                "profile",
                "-d",
                str(db_file),
                str(_find_sketch(work)),
                "-o",
                str(profile),
            ],
            timeout=600,
            name="sylph profile failed",
        )
        species = parse_profile(profile, taxa_map)

    return SylphResult(
        database={"name": db_file.name, "path": str(db_file)},
        result={"species": species, "n_species": len(species)},
    )
