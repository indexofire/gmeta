"""End-to-end coverage: minimap2 + samtools against tiny fixtures.

Skipped automatically when the binaries (pixi env) are unavailable.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gmeta.analysis.coverage import coverage_for_species, coverage_per_species

pytestmark = pytest.mark.skipif(
    not (shutil.which("minimap2") and shutil.which("samtools")),
    reason="minimap2/samtools not on PATH",
)

# References are read-matching heads plus a distinct tail so each read aligns
# to exactly one position (periodic references would scatter primary hits).
_READ_A = "ACGTACGTAC" * 6  # 60 bp
_READ_B = "TTTTGGGGCC" * 6  # 60 bp
REF_A = ">refA\n" + _READ_A + "A" * 60 + "\n"  # 120 bp, read head + A-tail
REF_B = ">refB\n" + _READ_B + "G" * 20 + "\n"  # 80 bp, read head + G-tail

# Reads of 60 bp (minimap2 -x sr needs ≥50 bp): 5 cover refA positions 0-59,
# 3 cover refB positions 0-59.
READS_R1 = "".join(f"@r{i}\n{_READ_A}\n+\n{'I' * 60}\n" for i in range(5)) + "".join(
    f"@s{i}\n{_READ_B}\n+\n{'I' * 60}\n" for i in range(3)
)


@pytest.fixture
def ref_a(tmp_path: Path) -> Path:
    path = tmp_path / "GCF_A.1_ref.fna"
    path.write_text(REF_A)
    return path


@pytest.fixture
def ref_b(tmp_path: Path) -> Path:
    path = tmp_path / "GCF_B.1_ref.fna"
    path.write_text(REF_B)
    return path


@pytest.fixture
def fastq(tmp_path: Path) -> Path:
    path = tmp_path / "sample_R1.fastq"
    path.write_text(READS_R1)
    return path


def test_combined_coverage(ref_a: Path, ref_b: Path, fastq: Path, tmp_path: Path) -> None:
    stats = coverage_for_species(
        [fastq], [("A", ref_a), ("B", ref_b)], threads=1, min_depths=(1, 5), work_dir=tmp_path / "w"
    )
    a = stats["A"]
    assert a.reference_length == 120
    # 5 reads × 60 bp cover refA positions 0..59 at depth 5 → 50% of 120 bp
    assert a.pct_covered[1] == pytest.approx(50.0)
    assert a.pct_covered[5] == pytest.approx(50.0)
    assert a.mean_depth == pytest.approx(300 / 120)  # 5 reads × 60 bp / 120 bp

    b = stats["B"]
    assert b.reference_length == 80
    assert b.pct_covered[1] == pytest.approx(75.0)  # 3×60 bp over positions 0..59
    assert b.pct_covered[5] == pytest.approx(0.0)


def test_per_species_coverage_matches_combined(
    ref_a: Path, ref_b: Path, fastq: Path, tmp_path: Path
) -> None:
    combined = coverage_for_species(
        [fastq], [("A", ref_a), ("B", ref_b)], threads=1, min_depths=(1,), work_dir=tmp_path / "w1"
    )
    independent = coverage_per_species(
        [fastq], [("A", ref_a), ("B", ref_b)], threads=1, min_depths=(1,), work_dir=tmp_path / "w2"
    )
    for key in ("A", "B"):
        assert combined[key].pct_covered[1] == pytest.approx(independent[key].pct_covered[1])
