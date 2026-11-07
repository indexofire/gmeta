"""`gmeta db fetch` script generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from gmeta.dbfetch import TARGETS, write_fetch_scripts


def test_writes_scripts_and_run_all(tmp_path: Path) -> None:
    written = write_fetch_scripts(["kraken2", "kaiju", "kmcp"], tmp_path, "/data/db")
    names = {p.name for p in written}
    assert names == {"fetch-kraken2.sh", "fetch-kaiju.sh", "fetch-kmcp.sh", "run_all.sh"}
    for script in written:
        assert script.stat().st_mode & 0o111  # executable


def test_script_content(tmp_path: Path) -> None:
    (write_fetch_scripts(["kraken2"], tmp_path, "/data/db"))
    body = (tmp_path / "fetch-kraken2.sh").read_text()

    assert "set -euo pipefail" in body
    assert 'DB_ROOT="${GMETA_DB_DIR:-/data/db}"' in body
    assert "minikraken2_v2_8GB_201904_UPDATE.tgz" in body
    assert "kmer_distrib" in body  # bracken verification
    assert "gmeta db list" in body


def test_kmcp_script_documents_manual_step(tmp_path: Path) -> None:
    write_fetch_scripts(["kmcp"], tmp_path, "/data/db")
    body = (tmp_path / "fetch-kmcp.sh").read_text()

    assert "ACTION REQUIRED" in body
    assert "bioinf.shenwei.me/kmcp/database/" in body
    assert "new_taxdump.tar.gz" in body  # taxdump auto-downloaded


def test_metaphlan_script_uses_installer(tmp_path: Path) -> None:
    write_fetch_scripts(["metaphlan"], tmp_path, "/data/db")
    body = (tmp_path / "fetch-metaphlan.sh").read_text()
    assert "metaphlan --install --bowtie2db" in body


def test_unknown_target_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown fetch target"):
        write_fetch_scripts(["nope"], tmp_path, "/data/db")


def test_all_targets_have_scripts(tmp_path: Path) -> None:
    written = write_fetch_scripts(sorted(TARGETS), tmp_path, "/data/db")
    assert len(written) == len(TARGETS) + 1  # + run_all.sh


def test_cli_db_fetch(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from gmeta.cli import main

    result = CliRunner().invoke(
        main, ["db", "fetch", "kaiju", "-O", str(tmp_path / "s"), "--db-root", str(tmp_path / "db")]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "s" / "fetch-kaiju.sh").is_file()


def test_cli_db_fetch_bad_target(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from gmeta.cli import main

    result = CliRunner().invoke(main, ["db", "fetch", "nope"])
    assert result.exit_code != 0
