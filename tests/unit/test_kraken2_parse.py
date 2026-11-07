"""Kraken2 kreport / bracken parsing."""

from __future__ import annotations

from pathlib import Path

from gmeta.analysis.kraken2 import KreportSummary, parse_bracken, parse_kreport


def test_parse_kreport_totals(kreport_file: Path) -> None:
    summary = parse_kreport(kreport_file)
    assert summary.total_reads == 140000
    assert summary.classified_reads == 100000
    assert summary.unclassified_reads == 40000
    assert 0 < summary.classified_fraction < 1


def test_parse_kreport_species_rank_sorted(kreport_file: Path) -> None:
    species = parse_kreport(kreport_file).at_rank("species")
    names = [row.name for row in species]
    assert names == [
        "Homo sapiens",
        "Vibrio cholerae",
        "Escherichia coli",
        "Vibrio parahaemolyticus",
    ]


def test_parse_kreport_keeps_subspecies_code(kreport_file: Path) -> None:
    summary = parse_kreport(kreport_file)
    assert any(row.rank == "S1" and row.name == "Vibrio cholerae O1" for row in summary.rows)


def test_parse_kreport_genus_context(kreport_file: Path) -> None:
    genus = parse_kreport(kreport_file).at_rank("genus")
    assert [row.name for row in genus] == ["Vibrio"]
    assert genus[0].reads_total == 29500


def test_parse_kreport_depth_tree(kreport_file: Path) -> None:
    summary = parse_kreport(kreport_file)
    by_name = {row.name: row for row in summary.rows}
    assert by_name["Vibrio"].depth < by_name["Vibrio cholerae"].depth
    assert by_name["Vibrio cholerae O1"].depth > by_name["Vibrio cholerae"].depth


def test_kreport_roundtrip_dict(kreport_file: Path) -> None:
    summary: KreportSummary = parse_kreport(kreport_file)
    payload = summary.to_dict()
    assert payload["total_reads"] == summary.total_reads
    assert len(payload["rows"]) == len(summary.rows)


def test_parse_bracken_species_only_and_sorted(bracken_file: Path) -> None:
    rows = parse_bracken(bracken_file)
    names = [row["name"] for row in rows]
    assert names[0] == "Homo sapiens"  # 40% fraction
    assert "Vibrio" not in names  # genus-level rows dropped
    cholera = next(row for row in rows if row["name"] == "Vibrio cholerae")
    assert cholera["reads"] == 25000
    assert cholera["fraction"] == 0.25  # normalised to 0..1


def test_parse_bracken_confidence_bands(bracken_file: Path) -> None:
    rows = parse_bracken(bracken_file)
    by_name = {row["name"]: row for row in rows}
    assert by_name["Homo sapiens"]["confidence"] == "high"  # 40%
    assert by_name["Escherichia coli"]["confidence"] == "medium"  # 8%
    assert by_name["Vibrio parahaemolyticus"]["confidence"] == "low"  # 1.5%
