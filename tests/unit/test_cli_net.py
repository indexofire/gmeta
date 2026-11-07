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
    # 4 species in the fixture
    assert ws.max_row == 5


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
