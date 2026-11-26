"""On-demand reference acquisition (ensure_references) with a fake CLI."""

from __future__ import annotations

import os
from pathlib import Path

from gmeta.refgenomes import ensure_references, find_assembly, parse_summary

FAKE_SUMMARY_JSONL = (
    '{"accession":"GCF_000005845.2","organism":'
    '{"organism_name":"Escherichia coli str. K-12, substr. MG1655"}}\n'
)
FAKE_SUMMARY_PRETTY = (
    '{\n  "reports": [\n    {"accession": "GCF_000005845.2", "organism": '
    '{"organism_name": "Escherichia coli str. K-12, substr. MG1655"}}\n  ]\n}\n'
)


def test_parse_summary_shapes() -> None:
    # commas are replaced with spaces for CSV safety
    expected = ("GCF_000005845.2", "Escherichia coli str. K-12  substr. MG1655")
    assert parse_summary(FAKE_SUMMARY_JSONL) == expected
    assert parse_summary(FAKE_SUMMARY_PRETTY) == expected
    assert parse_summary("") is None
    assert parse_summary('{"reports": []}') is None


def _fake_datasets(bin_dir: Path, count_file: Path, fail_taxid: str = "") -> None:
    fake = bin_dir / "datasets"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "summary" ]; then\n'
        f'  if [ "$4" = "{fail_taxid}" ] && [ -n "{fail_taxid}" ]; then\n'
        '    echo "Error: taxon not found" >&2; exit 1\n'
        "  fi\n"
        '  if [ "$3" != "taxon" ]; then\n'
        '    echo "Error: unknown command \\"$3\\"" >&2; exit 1\n'
        "  fi\n"
        f"  echo '{FAKE_SUMMARY_JSONL.strip()}'\n"
        'elif [ "$1" = "download" ]; then\n'
        f'  echo x >> "{count_file}"\n'
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


def test_ensure_references_downloads_then_caches(tmp_path: Path, monkeypatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    count_file = tmp_path / "downloads.txt"
    _fake_datasets(bin_dir, count_file)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")

    refs = tmp_path / "refs"
    ready, errors = ensure_references([562], refs)
    assert errors == []
    assert ready[562] == refs / "562_GCF_000005845.2.fna"
    assert (refs / "562_GCF_000005845.2.fna").read_text().startswith(">chr1")
    manifest = (refs / "manifest.csv").read_text()
    assert "GCF_000005845.2,562,562," in manifest

    # second run: cached file, no new download
    ready2, errors2 = ensure_references([562], refs)
    assert errors2 == [] and 562 in ready2
    assert count_file.read_text().count("x") == 1


def test_ensure_references_reports_cli_errors(tmp_path: Path, monkeypatch) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    count_file = tmp_path / "downloads.txt"
    _fake_datasets(bin_dir, count_file, fail_taxid="999")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")

    ready, errors = ensure_references([999], tmp_path / "refs")
    assert ready == {}
    assert errors and "taxid 999" in errors[0]
    assert "taxon not found" in errors[0]


def test_find_assembly_falls_back_to_taxon_only(tmp_path: Path, monkeypatch) -> None:
    """Flag dialect: modern flags rejected → taxon alone still works."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "datasets"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "summary" ]; then\n'
        '  for a in "$@"; do\n'
        '    [ "$a" = "--as-json-lines" ] && { echo "unknown flag" >&2; exit 1; }\n'
        "  done\n"
        f"  echo '{FAKE_SUMMARY_JSONL.strip()}'\n"
        "fi\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    assert find_assembly(str(fake), "562")[0] == "GCF_000005845.2"


def test_ensure_references_missing_cli_says_how_to_install(tmp_path: Path, monkeypatch) -> None:
    import pytest

    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with pytest.raises(RuntimeError, match="ncbi-datasets-cli"):
        ensure_references([562], tmp_path / "refs")
