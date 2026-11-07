"""fastp JSON and bowtie2 stats parsing."""

from __future__ import annotations

from pathlib import Path

from gmeta.analysis.host import parse_bowtie2_stats
from gmeta.analysis.qc import parse_fastp_json

BOWTIE2_STDERR = """50000 reads; of these:
  50000 (100.00%) were paired; of these:
    30000 (60.00%) aligned concordantly 0 times
    18000 (36.00%) aligned concordantly exactly 1 time
    2000 (4.00%) aligned concordantly >1 times
70.00% overall alignment rate
"""


def test_parse_fastp_paired_reads_doubled(fastp_json_file: Path) -> None:
    qc = parse_fastp_json(fastp_json_file)
    assert qc.total_reads == 100000  # 50k pairs × 2
    assert qc.clean_reads == 96000
    assert qc.total_bases == 7500000
    assert qc.clean_bases == 7000000
    assert qc.q30_rate == 0.95
    assert qc.duplication_rate == 0.12
    assert qc.read1_mean_length == 150


def test_parse_fastp_filtering_result(fastp_json_file: Path) -> None:
    qc = parse_fastp_json(fastp_json_file)
    assert qc.filtering_result["too_short_reads"] == 400


def test_parse_bowtie2_paired() -> None:
    stats = parse_bowtie2_stats(BOWTIE2_STDERR, paired=True)
    assert stats.total_reads == 100000  # 50k pairs × 2
    assert stats.host_rate == 0.70
    assert stats.host_reads == 70000
    assert stats.clean_reads == 30000


def test_parse_bowtie2_single_end() -> None:
    text = "1000 reads; of these:\n  1000 (100.00%) were unpaired\n25.00% overall alignment rate\n"
    stats = parse_bowtie2_stats(text, paired=False)
    assert stats.total_reads == 1000
    assert stats.host_reads == 250
    assert stats.clean_reads == 750


def test_parse_bowtie2_rejects_garbage() -> None:
    import pytest

    with pytest.raises(ValueError):
        parse_bowtie2_stats("not a bowtie2 log", paired=False)
