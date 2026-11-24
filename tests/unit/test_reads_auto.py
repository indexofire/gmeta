"""Auto-detection of a sample's FASTQ files (non-standard naming fallback)."""

from __future__ import annotations

from pathlib import Path

from gmeta.analysis.coverage import discover_reads_auto


def _fastq(path: Path) -> Path:
    path.write_text("@r1\nACGT\n+\nIIII\n")
    return path


def test_paired_standard_names(tmp_path: Path) -> None:
    _fastq(tmp_path / "S1_R1.fastq.gz")
    _fastq(tmp_path / "S1_R2.fastq.gz")
    assert discover_reads_auto(tmp_path, "S1") == [
        str(tmp_path / "S1_R1.fastq.gz"),
        str(tmp_path / "S1_R2.fastq.gz"),
    ]


def test_alternate_mate_styles(tmp_path: Path) -> None:
    # .1/.2 style
    _fastq(tmp_path / "S2.1.fq.gz")
    _fastq(tmp_path / "S2.2.fq.gz")
    found = discover_reads_auto(tmp_path, "S2")
    assert found is not None and len(found) == 2

    # _R1_001 style
    _fastq(tmp_path / "S3_R1_001.fastq.gz")
    _fastq(tmp_path / "S3_R2_001.fastq.gz")
    found = discover_reads_auto(tmp_path, "S3")
    assert found is not None and len(found) == 2


def test_single_end_fallback(tmp_path: Path) -> None:
    _fastq(tmp_path / "S4.fq.gz")
    found = discover_reads_auto(tmp_path, "S4")
    assert found == [str(tmp_path / "S4.fq.gz")]

    _fastq(tmp_path / "S5_R1.fq.gz")  # mate 2 missing
    found = discover_reads_auto(tmp_path, "S5")
    assert found == [str(tmp_path / "S5_R1.fq.gz")]


def test_prefix_boundary(tmp_path: Path) -> None:
    """S1 must not pick up S10's files."""
    _fastq(tmp_path / "S10_R1.fq.gz")
    assert discover_reads_auto(tmp_path, "S1") is None

    _fastq(tmp_path / "S1_R1.fq.gz")
    found = discover_reads_auto(tmp_path, "S1")
    assert found == [str(tmp_path / "S1_R1.fq.gz")]


def test_no_match_and_missing_dir(tmp_path: Path) -> None:
    _fastq(tmp_path / "other_R1.fq.gz")
    assert discover_reads_auto(tmp_path, "S1") is None
    assert discover_reads_auto(tmp_path / "nowhere", "S1") is None
