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


def test_refs_script_needs_taxids(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="refs target needs"):
        write_fetch_scripts(["refs"], tmp_path, "/data/db")


def test_refs_script_content(tmp_path: Path) -> None:
    written = write_fetch_scripts(["refs"], tmp_path, "/data/db", refs_taxids=["562", "662"])
    body = (tmp_path / "fetch-refs.sh").read_text()
    assert written[0].name == "fetch-refs.sh"
    assert "datasets summary genome taxid" in body
    assert "datasets download genome accession" in body
    assert "for taxid in \\\n562\n662" in body
    assert "manifest.csv" in body
    assert "--ref-dir" in body
    # CLI (not the deprecated Python pylib) is the documented requirement
    assert "ncbi-datasets-cli" in body
    assert "pylib is deprecated" in body
    assert "--reference" in body  # prefer reference/representative assembly


def test_cli_db_fetch_refs(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from gmeta.cli import main

    result = CliRunner().invoke(
        main,
        [
            "db",
            "fetch",
            "refs",
            "--taxids",
            "562, 662",
            "-O",
            str(tmp_path / "s"),
            "--db-root",
            str(tmp_path / "db"),
        ],
    )
    assert result.exit_code == 0, result.output
    body = (tmp_path / "s" / "fetch-refs.sh").read_text()
    assert "\n562\n662" in body


def test_cli_db_fetch_refs_from_missing_tsv(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from gmeta.cli import main

    missing = tmp_path / "missing.tsv"
    missing.write_text(
        "sample_id\ttaxid\tspecies_latin\tspecies_cn\tspecies_reads\n"
        "S1\t1304\tStreptococcus salivarius\t唾液链球菌\t11848179\n"
        "S2\t1304\tStreptococcus salivarius\t唾液链球菌\t100\n"
        "S2\t662\tVibrio cholerae\tVibrio cholerae\t50\n"
    )
    result = CliRunner().invoke(
        main,
        [
            "db",
            "fetch",
            "refs",
            "--missing-refs",
            str(missing),
            "-O",
            str(tmp_path / "s"),
            "--db-root",
            str(tmp_path / "db"),
        ],
    )
    assert result.exit_code == 0, result.output
    body = (tmp_path / "s" / "fetch-refs.sh").read_text()
    assert "\n1304\n662" in body  # de-duplicated, order kept


def test_cli_db_fetch_refs_requires_input(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from gmeta.cli import main

    result = CliRunner().invoke(main, ["db", "fetch", "refs"])
    assert result.exit_code != 0
    assert "--taxids or --missing-refs" in result.output


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
