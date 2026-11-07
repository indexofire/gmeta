"""Batch sample grouping and manifest parsing — ported from gside's meta layer.

Two ways to express a batch (both land in ``[{id, files}]``):

* positional reads — exactly two files form one historic pair; more files
  are grouped by mate marker (``A_R1 A_R2 B_R1 B_R2`` → two samples)
* ``--samples`` manifest — ``sample_id<TAB>reads [<TAB>reads2]`` per line
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_FASTA_SUFFIXES = (".fna", ".fa", ".fasta")
_FASTQ_SUFFIXES = (".fq", ".fastq")

_MATE_RE = re.compile(r"^(.*?)[._-](?:R)?([12])(?:_001)?$", re.IGNORECASE)


def input_kind(path: str) -> str:
    """'fasta' / 'fastq' / 'unknown' from the extension (``.gz`` aware)."""
    name = str(path).lower()
    for suffix in (".gz", ".bz2"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    if name.endswith(_FASTA_SUFFIXES):
        return "fasta"
    if name.endswith(_FASTQ_SUFFIXES):
        return "fastq"
    return "unknown"


def mate_key(path: str) -> tuple[str, int] | None:
    """``S_R1.fq.gz`` → ``("S", 1)``; None when the name has no mate marker."""
    name = Path(path).name
    for suffix in (".gz", ".bz2"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
    for suffix in (".fastq", ".fq"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    match = _MATE_RE.match(name)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def group_read_samples(files: list[str]) -> list[list[str]]:
    """Group FASTQ mates (``_R1/_R2``, ``_1/_2``, ``.1/.2``) into one sample.

    Order follows first occurrence; mate 1 precedes mate 2. Files without a
    mate marker, FASTA files, and unmatched mates become single-file samples.
    """
    keyed = [(mate_key(f) if input_kind(f) == "fastq" else None, f) for f in files]
    bases: dict[str, dict[int, str]] = {}
    for key, path in keyed:
        if key:
            bases.setdefault(key[0].lower(), {})[key[1]] = path

    samples: list[list[str]] = []
    emitted: set[str] = set()
    for key, path in keyed:
        if key is None:
            samples.append([path])
            continue
        base = key[0].lower()
        if base in emitted:
            continue
        mates = bases[base]
        if 1 in mates and 2 in mates:
            samples.append([mates[1], mates[2]])
        else:
            samples.append([mates[1] if 1 in mates else mates[2]])
        emitted.add(base)
    return samples


def group_batch_samples(paths: list[str]) -> list[list[str]]:
    """Group positional batch inputs (the gside ``--meta`` contract).

    Exactly two files are one sample (historic positional pairing); more
    files are grouped by mate marker.
    """
    if len(paths) == 2:
        return [paths]
    return group_read_samples(paths)


def sample_id(files: list[str]) -> str:
    """Stable sample id for positional batches (``A_R1.fq`` → ``A``)."""
    first = Path(files[0]).name
    key = mate_key(files[0])
    if key:
        return key[0]
    for suffix in (".gz", ".bz2"):
        if first.lower().endswith(suffix):
            first = first[: -len(suffix)]
    for suffix in (".fastq", ".fq", ".fna", ".fa", ".fasta"):
        if first.lower().endswith(suffix):
            first = first[: -len(suffix)]
            break
    return first


def unique_ids(samples: list[list[str]]) -> list[str]:
    """Sample ids for grouped inputs, de-duplicated with ``_2``/``_3`` suffixes."""
    used: set[str] = set()
    ids: list[str] = []
    for files in samples:
        base = sample_id(files)
        candidate, n = base, 2
        while candidate in used:
            candidate = f"{base}_{n}"
            n += 1
        used.add(candidate)
        ids.append(candidate)
    return ids


def read_samples_manifest(path: str | Path) -> list[dict[str, Any]]:
    """Parse a ``sample_id<TAB>r1[<TAB>r2]`` manifest (header optional)."""
    manifest = Path(path)
    if not manifest.is_file():
        raise ValueError(f"samples manifest not found: {manifest}")
    samples: list[dict[str, Any]] = []
    seen: set[str] = set()
    for lineno, line in enumerate(manifest.read_text().splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cols = [c.strip() for c in line.split("\t")]
        if lineno == 1 and cols[0].lower() in ("sample", "sample_id"):
            continue
        if len(cols) < 2 or not cols[0] or not cols[1]:
            raise ValueError(f"{manifest}:{lineno}: expected sample_id<TAB>reads [<TAB>reads2]")
        if len(cols) > 3:
            raise ValueError(f"{manifest}:{lineno}: too many columns (max 3)")
        sample_id_ = cols[0]
        if sample_id_ in seen:
            raise ValueError(f"{manifest}:{lineno}: duplicate sample id {sample_id_!r}")
        seen.add(sample_id_)
        samples.append({"id": sample_id_, "files": [c for c in cols[1:] if c]})
    if not samples:
        raise ValueError(f"{manifest}: no samples found")
    return samples


def manifest_from_positional(paths: list[str]) -> list[dict[str, Any]]:
    """Grouped positional reads → manifest-shaped ``[{id, files}]``."""
    grouped = group_batch_samples(paths)
    return [
        {"id": sample_id_, "files": files}
        for sample_id_, files in zip(unique_ids(grouped), grouped, strict=True)
    ]


__all__ = [
    "group_batch_samples",
    "group_read_samples",
    "input_kind",
    "manifest_from_positional",
    "mate_key",
    "read_samples_manifest",
    "sample_id",
    "unique_ids",
]
