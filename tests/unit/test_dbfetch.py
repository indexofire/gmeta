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
    # official CLI path; both JSON-lines and pretty-JSON dialects tolerated
    assert "datasets summary genome taxid" in body
    assert "datasets download genome accession" in body
    assert "ncbi-datasets-cli" in body
    assert "--as-json-lines" in body
    assert "--reference" in body
    assert "parse_summary" in body
    assert "562\n662" in body
    assert "manifest.csv" in body
    assert "--ref-dir" in body
    assert "NCBI_API_KEY" in body  # optional rate-limit key
    assert "api.ncbi.nlm.nih.gov" not in body  # CLI, not the raw HTTP API


def test_generated_scripts_are_valid_bash(tmp_path: Path) -> None:
    """Regression: the taxid list must be syntactically valid bash."""
    import subprocess

    write_fetch_scripts(
        ["kraken2", "refs"],
        tmp_path,
        "/data/db",
        refs_taxids=["28132", "1304", "662"],
    )
    for script in tmp_path.glob("*.sh"):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, f"{script.name}: {result.stderr}"


def _fake_datasets(bin_dir) -> None:
    """A fake CLI covering both dialects; LEGACY/FAIL env switches the mode."""

    fake = bin_dir / "datasets"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "summary" ]; then\n'
        '  if [ -n "${FAIL:-}" ]; then echo "error: taxon not found" >&2; exit 1; fi\n'
        '  for a in "$@"; do\n'
        '    if [ "$a" = "--as-json-lines" ] && [ -n "${LEGACY:-}" ]; then\n'
        '      echo "unknown flag: --as-json-lines" >&2; exit 1\n'
        "    fi\n"
        "  done\n"
        '  if [ -n "${LEGACY:-}" ]; then\n'
        '    printf \'{\\n  "reports": [\\n    {"accession": "GCF_000005845.2", "organism": '
        '{\\"organism_name\\": \\"Escherichia coli str. K-12, substr. MG1655\\"}}\\n  ]\\n}\\n\'\n'
        "  else\n"
        '    printf \'{"accession":"GCF_000005845.2","organism":'
        '{"organism_name":"Escherichia coli str. K-12, substr. MG1655"}}\\n\'\n'
        "  fi\n"
        'elif [ "$1" = "download" ]; then\n'
        '  out=""; prev=""\n'
        '  for a in "$@"; do [ "$prev" = "--filename" ] && out="$a"; prev="$a"; done\n'
        '  python3 - "$out" <<PY\n'
        "import sys, zipfile\n"
        "with zipfile.ZipFile(sys.argv[1], 'w') as z:\n"
        "    z.writestr('ncbi_dataset/data/GCF_000005845.2/"
        "GCF_000005845.2_genomic.fna', '>chr1\\nACGTACGT\\n')\n"
        "PY\n"
        "fi\n"
    )
    fake.chmod(0o755)


def _run_refs_script(tmp_path, monkeypatch, **env):
    import os
    import subprocess

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _fake_datasets(bin_dir)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    write_fetch_scripts(["refs"], tmp_path / "s", str(tmp_path / "db"), refs_taxids=["562"])
    return subprocess.run(
        ["bash", str(tmp_path / "s" / "fetch-refs.sh")], capture_output=True, text=True
    )


def test_refs_script_end_to_end(tmp_path: Path, monkeypatch) -> None:
    """Modern CLI dialect: --as-json-lines emits one report per line."""
    result = _run_refs_script(tmp_path, monkeypatch)
    assert result.returncode == 0, result.stderr
    assert "WARN" not in result.stderr

    refs = tmp_path / "db" / "refs"
    assert (refs / "562_GCF_000005845.2.fna").is_file()
    manifest = (refs / "manifest.csv").read_text()
    assert manifest.splitlines()[0].startswith("accession,species_taxid")
    assert "GCF_000005845.2,562,562," in manifest
    assert "Escherichia coli" in manifest


def test_refs_script_legacy_cli_dialect(tmp_path: Path, monkeypatch) -> None:
    """Older CLI: rejects --as-json-lines and prints a pretty JSON document."""
    result = _run_refs_script(tmp_path, monkeypatch, LEGACY="1")
    assert result.returncode == 0, result.stderr
    assert "WARN" not in result.stderr
    assert (tmp_path / "db" / "refs" / "562_GCF_000005845.2.fna").is_file()
    assert "GCF_000005845.2,562,562," in (tmp_path / "db" / "refs" / "manifest.csv").read_text()


def test_refs_script_cli_failure_surfaces_error(tmp_path: Path, monkeypatch) -> None:
    result = _run_refs_script(tmp_path, monkeypatch, FAIL="1")
    assert result.returncode == 0  # batch keeps going
    assert "WARN: no NCBI assembly for taxid 562" in result.stderr
    assert "CLI:" in result.stderr  # the CLI's own error is shown, not swallowed
    assert "taxon not found" in result.stderr


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
