"""Per-species genome coverage via minimap2 + samtools.

Ported from the standalone ``calculate_coverage.py`` used for 国家致病菌识别网
reporting, rewritten as streaming pure Python (no numpy/pandas): depth lines
are aggregated on the fly, so memory stays constant regardless of genome size.

Two modes mirror the original script:

* combined (default) — one concatenated reference per sample, one alignment;
  ~10× faster for multi-species samples, but reads mapping equally well to
  several species are assigned to one best match only.
* per-species — one alignment per reference, strictly independent estimates.
"""

from __future__ import annotations

import csv
import gzip
import shlex
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gmeta.config import which
from gmeta.engine._env import require_bin

_MINIMAP2_HINT = "minimap2 not found — pixi add minimap2"
_SAMTOOLS_HINT = "samtools not found — pixi add samtools"

_DEFAULT_MIN_DEPTHS = (1, 5, 10)

# seq ids inside a combined reference: "{key}__{idx}"
_SEQ_ID_SEP = "__"


@dataclass
class CoverageStats:
    """Depth statistics for one species' reference genome (percent 0..100)."""

    reference_length: int = 0
    mean_depth: float = 0.0
    pct_covered: dict[int, float] = field(default_factory=dict)  # threshold → %

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_length": self.reference_length,
            "mean_depth": round(self.mean_depth, 4),
            **{f"pct_covered_{d}x": round(pct, 4) for d, pct in self.pct_covered.items()},
        }


@dataclass
class ManifestEntry:
    accession: str
    species_taxid: int
    scientific_name: str
    file_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "accession": self.accession,
            "species_taxid": self.species_taxid,
            "scientific_name": self.scientific_name,
            "file_path": str(self.file_path),
        }


def load_manifest(path: str | Path) -> dict[int, ManifestEntry]:
    """Reference-genome manifest → {species_taxid: entry}.

    Manifest columns: accession,species_taxid,organism_taxid,scientific_name,
    file_path. Relative paths resolve against the manifest's directory.
    """
    manifest_path = Path(path)
    base = manifest_path.parent
    entries: dict[int, ManifestEntry] = {}
    with manifest_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                taxid = int(row["species_taxid"])
            except (KeyError, TypeError, ValueError):
                continue
            file_path = Path(row.get("file_path") or "")
            if not file_path.is_absolute():
                file_path = base / file_path
            entries[taxid] = ManifestEntry(
                accession=(row.get("accession") or "").strip(),
                species_taxid=taxid,
                scientific_name=(row.get("scientific_name") or "").strip(),
                file_path=file_path,
            )
    return entries


def resolve_reference(
    taxid: int,
    manifest: dict[int, ManifestEntry] | None,
    ref_dir: str | Path | None,
) -> tuple[ManifestEntry | None, Path | None]:
    """Resolve a reference genome for a species taxid.

    Order: manifest entry (its own ``file_path``, or ``{accession}*.fna``
    inside ``ref_dir`` when given) → ``{taxid}*.fna`` glob in ``ref_dir``.
    Returns ``(entry_or_None, fasta_path_or_None)``.
    """
    entry = (manifest or {}).get(taxid)
    if entry is not None:
        candidates: list[Path] = []
        if ref_dir is not None and entry.accession:
            candidates = sorted(Path(ref_dir).glob(f"{entry.accession}*.fna"))
        if candidates:
            return entry, candidates[0]
        if entry.file_path.is_file():
            return entry, entry.file_path
        return entry, None
    if ref_dir is not None:
        candidates = sorted(Path(ref_dir).glob(f"{taxid}*.fna"))
        if candidates:
            return None, candidates[0]
    return None, None


def fasta_sequence_lengths(path: str | Path) -> dict[str, int]:
    """FASTA → {seq_id: length}; gzip-aware, streams the file."""
    lengths: dict[str, int] = {}
    current: str | None = None
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as fh:  # type: ignore[operator]
        for line in fh:
            if line.startswith(">"):
                current = line[1:].split()[0]
                lengths[current] = 0
            elif current is not None:
                lengths[current] += len(line.strip())
    return lengths


def _align_sorted(
    ref_fasta: Path,
    reads: Sequence[str | Path],
    bam_out: Path,
    threads: int,
    preset: str = "sr",
) -> None:
    """minimap2 -ax … | samtools sort → sorted BAM (no index needed for depth)."""
    minimap2 = require_bin("minimap2", hint=_MINIMAP2_HINT, resolver=which)
    require_bin("samtools", hint=_SAMTOOLS_HINT, resolver=which)

    align_part = [
        minimap2,
        "-ax",
        preset,
        "-t",
        str(threads),
        str(ref_fasta),
        *[str(r) for r in reads],
    ]
    sort_part = ["samtools", "sort", "-@", str(threads), "-o", str(bam_out), "-"]
    cmd = (
        " ".join(shlex.quote(x) for x in align_part)
        + " | "
        + " ".join(shlex.quote(x) for x in sort_part)
    )
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="ignore")[:500]
        raise RuntimeError(f"minimap2/samtools sort failed: {detail}")


def _depth_stats_from_bam(
    bam_path: Path,
    seq_groups: dict[str, list[str]],  # group key → seq ids
    lengths: dict[str, int],
    min_depths: Sequence[int] = _DEFAULT_MIN_DEPTHS,
) -> dict[str, CoverageStats]:
    """Stream ``samtools depth -a`` and aggregate per group.

    ``-a`` emits every reference position (zero-depth included), so the
    per-group denominator is the group's total reference length.
    """
    group_len = {key: sum(lengths[seq] for seq in seqs) for key, seqs in seq_groups.items()}
    depth_sums = {key: 0 for key in seq_groups}
    covered = {key: {d: 0 for d in min_depths} for key in seq_groups}
    seq_to_group = {seq: key for key, seqs in seq_groups.items() for seq in seqs}

    proc = subprocess.Popen(
        ["samtools", "depth", "-a", str(bam_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    for raw in proc.stdout:
        fields = raw.decode().rstrip("\n").split("\t")
        if len(fields) != 3:
            continue
        seq_id = fields[0]
        key = seq_to_group.get(seq_id)
        if key is None:
            continue
        try:
            depth = int(fields[2])
        except ValueError:
            continue
        depth_sums[key] += depth
        counts = covered[key]
        for threshold in min_depths:
            if depth >= threshold:
                counts[threshold] += 1
    proc.stdout.close()
    stderr = proc.stderr.read().decode(errors="ignore") if proc.stderr else ""
    if proc.wait() != 0:
        raise RuntimeError(f"samtools depth failed: {stderr[:500]}")

    stats: dict[str, CoverageStats] = {}
    for key, total_len in group_len.items():
        if total_len == 0:
            stats[key] = CoverageStats(reference_length=0)
            continue
        stats[key] = CoverageStats(
            reference_length=total_len,
            mean_depth=depth_sums[key] / total_len,
            pct_covered={d: 100.0 * counts / total_len for d, counts in covered[key].items()},
        )
    return stats


def _build_combined_reference(
    entries: Sequence[tuple[str, Path]],  # (key, fasta path)
    out_fasta: Path,
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Concatenate references with unique ``{key}__{idx}`` sequence ids.

    Returns ``(seq_groups, lengths)`` — group key → seq ids, and seq id → length.
    """
    seq_groups: dict[str, list[str]] = {}
    lengths: dict[str, int] = {}
    with out_fasta.open("w") as out:
        for key, ref_path in entries:
            seq_ids: list[str] = []
            opener = gzip.open if str(ref_path).endswith(".gz") else open
            with opener(ref_path, "rt") as fh:  # type: ignore[operator]
                for line in fh:
                    if line.startswith(">"):
                        seq_id = f"{key}{_SEQ_ID_SEP}{len(seq_ids)}"
                        seq_ids.append(seq_id)
                        out.write(f">{seq_id}\n")
                        lengths[seq_id] = 0
                    elif seq_ids:
                        stripped = line.strip()
                        lengths[seq_ids[-1]] += len(stripped)
                        out.write(stripped + "\n")
            seq_groups[key] = seq_ids
    return seq_groups, lengths


def coverage_for_species(
    reads: Sequence[str | Path],
    entries: Sequence[tuple[str, Path]],
    threads: int = 4,
    min_depths: Sequence[int] = _DEFAULT_MIN_DEPTHS,
    work_dir: str | Path | None = None,
    preset: str = "sr",
) -> dict[str, CoverageStats]:
    """Coverage stats per entry key, aligning once against a combined reference.

    ``entries`` pairs a stable key (accession or taxid string) with a FASTA
    path. Reads can be one file (single-end) or two (paired).
    """
    if not entries:
        return {}

    if work_dir is not None:
        work = Path(work_dir)
        work.mkdir(parents=True, exist_ok=True)
    else:
        work = Path(tempfile.mkdtemp(prefix="gmeta-cov-"))

    combined = work / f"combined_{abs(hash(tuple(k for k, _ in entries)))}.fna"
    seq_groups, lengths = _build_combined_reference(entries, combined)
    bam_out = work / (combined.stem + ".sorted.bam")
    _align_sorted(combined, reads, bam_out, threads, preset=preset)
    stats = _depth_stats_from_bam(bam_out, seq_groups, lengths, min_depths)

    if work_dir is None:
        import shutil

        shutil.rmtree(work, ignore_errors=True)
    return stats


def coverage_per_species(
    reads: Sequence[str | Path],
    entries: Sequence[tuple[str, Path]],
    threads: int = 4,
    min_depths: Sequence[int] = _DEFAULT_MIN_DEPTHS,
    work_dir: str | Path | None = None,
    preset: str = "sr",
) -> dict[str, CoverageStats]:
    """Coverage per entry with strictly independent alignments (slower, exact)."""
    stats: dict[str, CoverageStats] = {}
    for key, ref_path in entries:
        single = coverage_for_species(
            reads,
            [(key, ref_path)],
            threads=threads,
            min_depths=min_depths,
            work_dir=work_dir,
            preset=preset,
        )
        stats.update(single)
    return stats


def discover_reads(
    reads_dir: str | Path,
    sample: str,
    pattern: str = "{sample}_R{pair}.fastq.gz",
) -> list[str] | None:
    """FASTQ paths for a sample; None when nothing is found.

    ``{pair}`` in the pattern means paired-end (expanded to 1/2); compressed
    and uncompressed variants are tried interchangeably.
    """
    base = Path(reads_dir)
    if "{pair}" in pattern:
        reads: list[str] = []
        for pair in ("1", "2"):
            candidate = pattern.format(sample=sample, pair=pair)
            found = _try_read_variants(base, candidate)
            if found is None:
                return None
            reads.append(str(found))
        return reads
    found = _try_read_variants(base, pattern.format(sample=sample))
    return [str(found)] if found else None


def _try_read_variants(base: Path, name: str) -> Path | None:
    candidate = base / name
    if candidate.exists():
        return candidate
    alt = name[:-3] if name.endswith(".gz") else name + ".gz"
    alt_path = base / alt
    return alt_path if alt_path.exists() else None


__all__ = [
    "CoverageStats",
    "ManifestEntry",
    "coverage_for_species",
    "coverage_per_species",
    "discover_reads",
    "fasta_sequence_lengths",
    "load_manifest",
    "resolve_reference",
]
