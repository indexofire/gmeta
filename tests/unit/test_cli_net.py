"""CLI surface for the 识别网 export command."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from openpyxl import load_workbook

from gmeta.cli import main


def test_net_build_from_kreport(kreport_file: Path, tmp_path: Path) -> None:
    target = tmp_path / "上报.xlsx"
    result = CliRunner().invoke(main, ["net", "build", str(kreport_file), "-o", str(target)])
    assert result.exit_code == 0, result.output

    wb = load_workbook(target)
    assert wb.sheetnames == ["混合样本", "审核明细"]
    ws = wb["混合样本"]
    assert ws.cell(row=1, column=1).value == "样本名称"
    assert ws.cell(row=2, column=1).value == kreport_file.stem
    # 4 species in the fixture, minus the host (Homo sapiens) → 3 rows
    assert ws.max_row == 4
    assert all(cell.value != "Homo sapiens" for row in ws.iter_rows(min_row=2) for cell in row)


def test_net_build_split_dir(kreport_file: Path, tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        [
            "net",
            "build",
            str(kreport_file),
            "-o",
            str(tmp_path / "all.xlsx"),
            "--split-dir",
            str(tmp_path / "per-sample"),
            "--top",
            "2",
        ],
    )
    assert result.exit_code == 0, result.output
    split = tmp_path / "per-sample" / f"{kreport_file.stem}.xlsx"
    assert split.is_file()
    ws = load_workbook(split).active
    assert ws.max_row == 3  # header + top-2


def test_net_build_requires_kreport(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["net", "build"])
    assert result.exit_code != 0


def test_net_build_bad_min_depths(kreport_file: Path, tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["net", "build", str(kreport_file), "-o", str(tmp_path / "x.xlsx"), "--min-depths", "a,b"],
    )
    assert result.exit_code != 0
    assert "min-depths" in result.output


def test_net_build_sample_id_override(kreport_file: Path, tmp_path: Path) -> None:
    """--sample-id fixes the reads matching when the artifact path lacks it."""
    target = tmp_path / "上报.xlsx"
    result = CliRunner().invoke(
        main,
        ["net", "build", str(kreport_file), "--sample-id", "1", "-o", str(target)],
    )
    assert result.exit_code == 0, result.output
    ws = load_workbook(target)["混合样本"]
    assert ws.cell(row=2, column=1).value == "1"


def test_net_build_sample_id_rejected_for_batch(kreport_file: Path, tmp_path: Path) -> None:
    other = tmp_path / "other.report"
    other.write_text(kreport_file.read_text())
    result = CliRunner().invoke(
        main,
        [
            "net",
            "build",
            str(kreport_file),
            str(other),
            "--sample-id",
            "1",
            "-o",
            str(tmp_path / "x.xlsx"),
        ],
    )
    assert result.exit_code != 0
    assert "single input" in result.output


def test_net_build_jobs_preserves_order(kreport_file: Path, tmp_path: Path) -> None:
    """--jobs processes samples concurrently but keeps the input order."""
    a = tmp_path / "A.report"
    b = tmp_path / "B.report"
    a.write_text(kreport_file.read_text())
    b.write_text(kreport_file.read_text())
    target = tmp_path / "batch.xlsx"
    result = CliRunner().invoke(
        main,
        ["net", "build", str(a), str(b), "-J", "2", "-o", str(target), "--top", "2"],
    )
    assert result.exit_code == 0, result.output
    ws = load_workbook(target)["混合样本"]
    samples = [ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)]
    # first row of each group carries the sample id, in input order
    assert [s for s in samples if s] == ["A", "B"]


def test_net_build_single_read_group_fallback(kreport_file: Path, tmp_path: Path) -> None:
    """No sample-id match, but only one read group in the dir → use it."""
    reads = tmp_path / "reads"
    reads.mkdir()
    (reads / "OTHER_R1.fq").write_text("@r\nACGT\n+\nIIII\n")
    (reads / "OTHER_R2.fq").write_text("@r\nACGT\n+\nIIII\n")

    result = CliRunner().invoke(
        main,
        [
            "net", "build", str(kreport_file),
            "--reads-dir", str(reads),
            "--top", "2",
            "-o", str(tmp_path / "x.xlsx"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "using the only reads group found: other" in result.output


def test_net_build_lists_read_group_candidates(kreport_file: Path, tmp_path: Path) -> None:
    reads = tmp_path / "reads"
    reads.mkdir()
    for base in ("ALPHA", "BETA"):
        (reads / f"{base}_R1.fq").write_text("@r\nACGT\n+\nIIII\n")
        (reads / f"{base}_R2.fq").write_text("@r\nACGT\n+\nIIII\n")

    result = CliRunner().invoke(
        main,
        [
            "net", "build", str(kreport_file),
            "--reads-dir", str(reads),
            "--top", "2",
            "-o", str(tmp_path / "x.xlsx"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "FASTQ groups in the dir" in result.output
    assert "alpha" in result.output and "beta" in result.output
