"""识别网 adapter for table-based profilers (centrifuge/kaiju/metaphlan/kmcp)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from gmeta.report.network import build_rows_from_profile, profile_to_network_rows


def _profile(tmp_path: Path, name: str, content: str):
    from gmeta.analysis.profilers import (
        parse_centrifuge_report,
        parse_kmcp_profile,
        parse_metaphlan_profile,
    )

    path = tmp_path / name
    path.write_text(content)
    if name.startswith("cf"):
        return parse_centrifuge_report(path)
    if name.startswith("mpa"):
        return parse_metaphlan_profile(path)
    return parse_kmcp_profile(path)


CENTRIFUGE_REPORT = """Escherichia\t562\tgenus\t4641652\t7227494\t100\t12.5
Escherichia coli\t561\tspecies\t4641652\t6428861\t90\t11.1
Vibrio\t641\tgenus\t5000000\t1000\t50\t0.02
Vibrio cholerae\t662\tspecies\t5000000\t900\t50\t0.01
"""

METAPHLAN_PROFILE = """#clade_name\tNCBI_tax_id\trelative_abundance\tadditional_species
g__Escherichia\t561\t55.5\t
s__Escherichia_coli\t562\t50.5\t
g__Vibrio\t641\t5.0\t
s__Vibrio_cholerae\t662\t4.2\t
"""

KMCP_PROFILE = (
    "#ref\tpercentage\tcoverage\tscore\tchunksFrac\tchunksRelDepth\tchunksRelDepthStd\t"
    "reads\tureads\thicureads\trefsize\trefname\ttaxid\trank\ttaxname\ttaxpath\ttaxpathsn\n"
    "GCF_000005845.2\t55.0\t0.95\t0.9\t0.9\t1.0\t0.01\t6400000\t6000000\t6000000\t4641652\t"
    "Escherichia coli\t562\tspecies\tEscherichia coli\t562\t1224|561|562\n"
    "GCF_000006925.2\t0.6\t0.90\t0.9\t0.9\t1.0\t0.01\t70000\t65000\t65000\t4550000\t"
    "Shigella flexneri\t630\tspecies\tShigella flexneri\t630\t1224|630\n"
)


def test_build_rows_from_profile_real_genus(tmp_path: Path) -> None:
    profile = _profile(tmp_path, "cf.txt", CENTRIFUGE_REPORT)
    rows = build_rows_from_profile(profile, "S1", top=10)
    by_latin = {row.species_latin: row for row in rows}

    ecoli = by_latin["Escherichia coli"]
    assert ecoli.genus_latin == "Escherichia"
    assert ecoli.genus_cn == "埃希氏菌属"
    assert ecoli.genus_reads == 7227494  # real genus row from centrifuge
    assert ecoli.species_cn == "大肠埃希氏菌"

    cholera = by_latin["Vibrio cholerae"]
    assert cholera.genus_reads == 1000


def test_build_rows_from_profile_metaphlan(tmp_path: Path) -> None:
    profile = _profile(tmp_path, "mpa.txt", METAPHLAN_PROFILE)
    rows = build_rows_from_profile(profile, "S1", top=10)
    by_latin = {row.species_latin: row for row in rows}
    assert by_latin["Escherichia coli"].genus_fraction == pytest_approx(0.555)
    assert by_latin["Vibrio cholerae"].species_fraction == pytest_approx(0.042)


def pytest_approx(value: float):
    import pytest

    return pytest.approx(value)


def test_build_rows_from_profile_kmcp_genus_aggregation(tmp_path: Path) -> None:
    profile = _profile(tmp_path, "kmcp.tsv", KMCP_PROFILE)
    rows = build_rows_from_profile(profile, "S1", top=10)
    by_latin = {row.species_latin: row for row in rows}

    ecoli = by_latin["Escherichia coli"]
    # no genus rows in kmcp → genus synthesised from species aggregation
    assert ecoli.genus_reads == 6400000
    assert ecoli.genus_latin == "Escherichia"

    flexneri = by_latin["Shigella flexneri"]
    assert flexneri.genus_latin == "Shigella"
    assert flexneri.genus_reads == 70000


def test_profile_to_network_rows_auto_detect(tmp_path: Path) -> None:
    path = tmp_path / "mpa.txt"
    path.write_text(METAPHLAN_PROFILE)
    rows, missing, detected = profile_to_network_rows(path, "S1", top=10)
    assert detected == "metaphlan"
    assert len(rows) == 2
    assert {row.species_latin for row in rows} == {"Escherichia coli", "Vibrio cholerae"}


def test_profile_to_network_rows_kraken_still_exact(tmp_path: Path, kreport_file: Path) -> None:
    rows, missing, detected = profile_to_network_rows(kreport_file, "S1", top=10)
    assert detected == "kraken2"
    by_latin = {row.species_latin: row for row in rows}
    assert by_latin["Vibrio cholerae"].genus_reads == 29500  # tree clade counts


def test_cli_net_build_metaphlan(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from gmeta.cli import main

    source = tmp_path / "SAMPLE_MPA.txt"
    source.write_text(METAPHLAN_PROFILE)
    target = tmp_path / "out.xlsx"
    result = CliRunner().invoke(main, ["net", "build", str(source), "-o", str(target)])
    assert result.exit_code == 0, result.output

    ws = load_workbook(target)["混合样本"]
    assert ws.cell(row=1, column=1).value == "样本名称"
    assert ws.cell(row=2, column=5).value == "大肠埃希氏菌"
    assert ws.cell(row=2, column=6).value == 0  # metaphlan reports no reads
    assert ws.cell(row=3, column=5).value == "Vibrio cholerae"  # fallback latin
    assert ws.cell(row=3, column=8).value == "4.20%"


def test_cli_report_metaphlan(tmp_path: Path) -> None:
    import json

    from click.testing import CliRunner

    from gmeta.cli import main

    source = tmp_path / "mpa.txt"
    source.write_text(METAPHLAN_PROFILE)
    result = CliRunner().invoke(main, ["report", "-s", "S1", "--metaphlan", str(source)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["method"] == "metaphlan"
    assert payload["n_species"] == 2
    names = {taxon["name"] for taxon in payload["taxa"]}
    assert "Vibrio cholerae" in names
