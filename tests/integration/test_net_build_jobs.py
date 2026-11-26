"""Concurrent net build: two samples with real minimap2+samtools coverage."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner
from openpyxl import load_workbook

from gmeta.cli import main

pytestmark = pytest.mark.skipif(
    not (shutil.which("minimap2") and shutil.which("samtools")),
    reason="minimap2/samtools not on PATH",
)

_read_a = "ACGTACGTAC" * 6  # 60 bp
_read_b = "TTTTGGGGCC" * 6
REF_A = ">chr1\n" + _read_a + "A" * 60 + "\n"  # 120 bp
REF_B = ">chr1\n" + _read_b + "G" * 60 + "\n"

KREPORT = """100.00\t1000\t0\tR\t1\troot
 60.00\t600\t600\tS\t562\t  Escherichia coli
 40.00\t400\t400\tU\t0\tunclassified
"""

KREPORT_B = """100.00\t1000\t0\tR\t1\troot
 60.00\t600\t600\tS\t662\t  Vibrio cholerae
 40.00\t400\t400\tU\t0\tunclassified
"""


def _fastq(path: Path, read: str, n: int = 6) -> None:
    qual = "I" * len(read)
    with path.open("w") as fh:
        for i in range(n):
            fh.write(f"@r{i}\n{read}\n+\n{qual}\n")


def test_net_build_jobs_with_coverage(tmp_path: Path) -> None:
    reads = tmp_path / "reads"
    reads.mkdir()
    _fastq(reads / "S1_R1.fastq", _read_a)
    _fastq(reads / "S2_R1.fastq", _read_b)

    refs = tmp_path / "refs"
    refs.mkdir()
    (refs / "562_GCF_1.fna").write_text(REF_A)
    (refs / "662_GCF_2.fna").write_text(REF_B)

    (tmp_path / "S1.report").write_text(KREPORT)
    (tmp_path / "S2.report").write_text(KREPORT_B)

    target = tmp_path / "batch.xlsx"
    result = CliRunner().invoke(
        main,
        [
            "net",
            "build",
            str(tmp_path / "S1.report"),
            str(tmp_path / "S2.report"),
            "--reads-dir",
            str(reads),
            "--ref-dir",
            str(refs),
            "--details",
            str(tmp_path / "details.tsv"),
            "-J",
            "2",
            "-t",
            "1",
            "-o",
            str(target),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "2/2 sample(s)" in result.output

    ws = load_workbook(target)["混合样本"]
    assert ws.cell(row=1, column=1).value == "样本名称"
    # two samples, one species row each, coverage filled (50% of 120 bp covered)
    assert ws.cell(row=2, column=1).value == "S1"
    assert ws.cell(row=2, column=7).value == pytest.approx(50.0)
    assert ws.cell(row=3, column=1).value == "S2"
    assert ws.cell(row=3, column=7).value == pytest.approx(50.0)

    details = (tmp_path / "details.tsv").read_text()
    assert details.count("已计算") == 2
