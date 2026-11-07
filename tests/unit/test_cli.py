"""CLI surface: version, help, report command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from gmeta import __version__
from gmeta.cli import main


def test_version_flag() -> None:
    result = CliRunner().invoke(main, ["-V"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_json_flag() -> None:
    result = CliRunner().invoke(main, ["-V", "-J"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["tool"] == "gmeta"


def test_help_lists_commands() -> None:
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ("run", "report", "db"):
        assert cmd in result.output


def test_report_stdout_json(bracken_file: Path, fastp_json_file: Path) -> None:
    result = CliRunner().invoke(
        main,
        [
            "report",
            "-s",
            "CLI-001",
            "--bracken",
            str(bracken_file),
            "--fastp-json",
            str(fastp_json_file),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["sample"]["sample_id"] == "CLI-001"
    assert payload["qc"]["total_reads"] == 100000
    assert payload["n_species"] == 4


def test_report_writes_html(bracken_file: Path, tmp_path: Path) -> None:
    target = tmp_path / "out" / "r.html"
    result = CliRunner().invoke(
        main,
        ["report", "-s", "CLI-002", "--bracken", str(bracken_file), "-o", str(target)],
    )
    assert result.exit_code == 0, result.output
    assert target.is_file()
    assert "CLI-002" in target.read_text()


def test_report_requires_input() -> None:
    result = CliRunner().invoke(main, ["report", "-s", "X"])
    assert result.exit_code != 0
    assert "bracken" in result.output


def test_db_list_json() -> None:
    result = CliRunner().invoke(main, ["db", "list", "-f", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "db_dir" in payload
    tools = set(payload["databases"])
    assert tools == {
        "kraken2",
        "centrifuge",
        "kaiju",
        "metaphlan",
        "kmcp",
        "sylph",
        "taxdump",
        "host",
    }
    # every entry carries the stable fields
    for entry in payload["databases"].values():
        assert set(entry) == {"path", "ready", "detail"}


def test_db_list_table_mentions_fetch() -> None:
    result = CliRunner().invoke(main, ["db", "list"])
    assert result.exit_code == 0
    assert "kraken2" in result.output
    assert "kmcp" in result.output
    assert "db fetch" in result.output
