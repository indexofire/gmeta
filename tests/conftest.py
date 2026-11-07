"""Shared fixtures: small but realistic profiler outputs for parser tests."""

from __future__ import annotations

from pathlib import Path

import pytest

KREPORT = """100.00	100000	0	R	1	root
 40.00	40000	40000	S	9606	  Homo sapiens
  8.00	8000	8000	S	562	  Escherichia coli
 30.00	29500	500	G	641	  Vibrio
 25.00	25000	25000	S	662	    Vibrio cholerae
  2.00	2000	2000	S1	1783561	      Vibrio cholerae O1
  1.50	1500	1500	S	670	    Vibrio parahaemolyticus
 40.00	40000	40000	U	0	unclassified
"""

BRACKEN = """name	tax_id	taxonomy_lvl	kraken_assigned_reads	added_reads	new_est_reads	fraction_total_reads
Vibrio cholerae	666	S	24000	1000	25000	25.00000
Homo sapiens	9606	S	40000	0	40000	40.00000
Escherichia coli	562	S	8000	0	8000	8.00000
Vibrio parahaemolyticus	670	S	500	0	500	0.50000
"""

FASTP_JSON = """{
  "summary": {
    "before_filtering": {"total_reads": 50000, "total_bases": 7500000, "q20_rate": 0.97, "q30_rate": 0.93},
    "after_filtering": {"total_reads": 48000, "total_bases": 7000000, "q20_rate": 0.98, "q30_rate": 0.95,
                        "read1_mean_length": 150, "read2_mean_length": 150}
  },
  "filtering_result": {"low_quality_reads": 1500, "too_many_N_reads": 100, "too_short_reads": 400},
  "duplication": {"rate": 0.12},
  "read1_before_filtering": {"total_reads": 50000},
  "read2_before_filtering": {"total_reads": 50000}
}
"""

BOWTIE2_STDERR = """50000 reads; of these:
  50000 (100.00%) were paired; of these:
    30000 (60.00%) aligned concordantly 0 times
    18000 (36.00%) aligned concordantly exactly 1 time
    2000 (4.00%) aligned concordantly >1 times
70.00% overall alignment rate
"""


@pytest.fixture
def kreport_file(tmp_path: Path) -> Path:
    path = tmp_path / "kreport.txt"
    path.write_text(KREPORT)
    return path


@pytest.fixture
def bracken_file(tmp_path: Path) -> Path:
    path = tmp_path / "bracken.txt"
    path.write_text(BRACKEN)
    return path


@pytest.fixture
def fastp_json_file(tmp_path: Path) -> Path:
    path = tmp_path / "fastp.json"
    path.write_text(FASTP_JSON)
    return path
