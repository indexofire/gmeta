"""Batch sample grouping and manifest parsing (ported from gside's meta layer)."""

from __future__ import annotations

from pathlib import Path

import pytest

from gmeta.samples import (
    group_batch_samples,
    group_read_samples,
    input_kind,
    manifest_from_positional,
    mate_key,
    read_samples_manifest,
    sample_id,
    unique_ids,
)


def test_input_kind() -> None:
    assert input_kind("a.fna") == "fasta"
    assert input_kind("a.fasta.gz") == "fasta"
    assert input_kind("a_R1.fastq.gz") == "fastq"
    assert input_kind("a.txt") == "unknown"


def test_mate_key_variants() -> None:
    assert mate_key("A_R1.fq.gz") == ("A", 1)
    assert mate_key("A_R2.fq") == ("A", 2)
    assert mate_key("B.1.fastq") == ("B", 1)
    assert mate_key("C-2.fq.gz") == ("C", 2)
    assert mate_key("D_001.fq.gz") is None
    assert mate_key("plain.fq") is None


def test_group_read_samples_pairs_and_singles() -> None:
    # order follows first occurrence: B_R1 introduces B before A's pair
    files = ["B_R1.fq", "A_R2.fq", "A_R1.fq", "solo.fq", "orphan_R1.fq"]
    grouped = group_read_samples(files)
    assert grouped == [["B_R1.fq"], ["A_R1.fq", "A_R2.fq"], ["solo.fq"], ["orphan_R1.fq"]]


def test_group_batch_samples_two_files_stay_one_sample() -> None:
    assert group_batch_samples(["a.fq", "b.fq"]) == [["a.fq", "b.fq"]]
    grouped = group_batch_samples(["A_R1.fq", "A_R2.fq", "B_R1.fq", "B_R2.fq"])
    assert grouped == [["A_R1.fq", "A_R2.fq"], ["B_R1.fq", "B_R2.fq"]]


def test_sample_id_from_filename() -> None:
    assert sample_id(["A_R1.fq.gz"]) == "A"
    assert sample_id(["sample.fastq.gz"]) == "sample"
    assert sample_id(["contigs.fna"]) == "contigs"


def test_unique_ids_deduplicates() -> None:
    ids = unique_ids([["A_R1.fq"], ["a_R2.fq"]])  # distinct case → distinct ids
    assert ids == ["A", "a"]
    ids = unique_ids([["A_R1.fq"], ["A.fq"]])  # same base → _2 suffix
    assert ids == ["A", "A_2"]


def test_manifest_roundtrip(tmp_path: Path) -> None:
    manifest = tmp_path / "samples.tsv"
    manifest.write_text("sample_id\treads\treads2\nS1\ts1_R1.fq\ts1_R2.fq\nS2\ts2.fq\n# comment\n")
    samples = read_samples_manifest(manifest)
    assert samples == [
        {"id": "S1", "files": ["s1_R1.fq", "s1_R2.fq"]},
        {"id": "S2", "files": ["s2.fq"]},
    ]


def test_manifest_rejects_duplicates_and_garbage(tmp_path: Path) -> None:
    bad = tmp_path / "bad.tsv"
    bad.write_text("S1\ta.fq\nS1\tb.fq\n")
    with pytest.raises(ValueError, match="duplicate"):
        read_samples_manifest(bad)

    empty = tmp_path / "empty.tsv"
    empty.write_text("# only comments\n")
    with pytest.raises(ValueError, match="no samples"):
        read_samples_manifest(empty)

    with pytest.raises(ValueError, match="not found"):
        read_samples_manifest(tmp_path / "missing.tsv")


def test_manifest_from_positional() -> None:
    manifest = manifest_from_positional(["A_R1.fq", "A_R2.fq", "B_R1.fq", "B_R2.fq"])
    assert manifest == [
        {"id": "A", "files": ["A_R1.fq", "A_R2.fq"]},
        {"id": "B", "files": ["B_R1.fq", "B_R2.fq"]},
    ]
