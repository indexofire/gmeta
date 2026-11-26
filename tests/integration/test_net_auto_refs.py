"""One-command flow: net build --auto-refs downloads references, then coverage."""

from __future__ import annotations

import os
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

_read = "ACGTACGTAC" * 6  # 60 bp
REF = ">chr1\n" + _read + "A" * 60 + "\n"  # 120 bp

KREPORT = """100.00\t1000\t0\tR\t1\troot
 60.00\t600\t600\tS\t562\t  Escherichia coli
 40.00\t400\t400\tU\t0\tunclassified
"""


def test_net_build_auto_refs_end_to_end(tmp_path: Path, monkeypatch) -> None:
    reads = tmp_path / "reads"
    reads.mkdir()
    qual = "I" * len(_read)
    with (reads / "S1_R1.fastq").open("w") as fh:
        for i in range(6):
            fh.write(f"@r{i}\n{_read}\n+\n{qual}\n")
    (tmp_path / "S1.report").write_text(KREPORT)

    # fake NCBI CLI: summary + a genome matching the reads
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "datasets"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "summary" ]; then\n'
        '  echo \'{"accession":"GCF_000005845.2","organism":'
        '{"organism_name":"Escherichia coli"}}\'\n'
        'elif [ "$1" = "download" ]; then\n'
        '  out=""; prev=""\n'
        '  for a in "$@"; do [ "$prev" = "--filename" ] && out="$a"; prev="$a"; done\n'
        '  python3 - "$out" <<PY\n'
        "import sys, zipfile\n"
        "with zipfile.ZipFile(sys.argv[1], 'w') as z:\n"
        f"    z.writestr('ncbi_dataset/data/GCF_000005845.2/x.fna', {REF!r})\n"
        "PY\n"
        "fi\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")

    refs = tmp_path / "refs"  # empty: everything must be fetched
    target = tmp_path / "auto.xlsx"
    result = CliRunner().invoke(
        main,
        [
            "net",
            "build",
            str(tmp_path / "S1.report"),
            "--reads-dir",
            str(reads),
            "--ref-dir",
            str(refs),
            "--auto-refs",
            "-t",
            "1",
            "-o",
            str(target),
            "--details",
            str(tmp_path / "details.tsv"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "auto-refs: 1 species missing references" in result.output
    assert "auto-refs: 1/1 reference(s) ready" in result.output

    assert (refs / "562_GCF_000005845.2.fna").is_file()
    assert "GCF_000005845.2,562,562," in (refs / "manifest.csv").read_text()

    ws = load_workbook(target)["混合样本"]
    # coverage computed in the same command: 60/120 bp = 50%
    assert ws.cell(row=2, column=7).value == pytest.approx(50.0)
    assert "已计算" in (tmp_path / "details.tsv").read_text()


def test_net_build_auto_refs_requires_reads_dir(kreport_file: Path, tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["net", "build", str(kreport_file), "--auto-refs", "-o", str(tmp_path / "x.xlsx")],
    )
    assert result.exit_code != 0
    assert "--reads-dir" in result.output
