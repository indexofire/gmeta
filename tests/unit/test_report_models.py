"""Priority pathogen annotation and report model assembly."""

from __future__ import annotations

from pathlib import Path

from gmeta.report import build_report
from gmeta.report.models import TaxonRow
from gmeta.report.priority import annotate, lookup


def test_lookup_exact_and_case_insensitive() -> None:
    entry = lookup("Vibrio cholerae")
    assert entry is not None and entry["zh_name"] == "霍乱弧菌"
    assert lookup("vibrio CHOLERAE") == entry


def test_lookup_alias() -> None:
    assert lookup("Shigella sonnei") is not None


def test_lookup_unknown_returns_none() -> None:
    assert lookup("Pseudomonas putida") is None


def test_annotate_sets_priority_fields() -> None:
    rows = annotate(
        [
            TaxonRow(name="Vibrio cholerae", fraction=0.25),
            TaxonRow(name="Pseudomonas putida", fraction=0.02),
        ]
    )
    assert rows[0].priority is True
    assert "霍乱弧菌" in (rows[0].priority_category or "")
    assert rows[1].priority is False
    assert rows[1].priority_category is None


def test_build_report_bracken_with_priority(
    bracken_file: Path, kreport_file: Path, fastp_json_file: Path
) -> None:
    report = build_report(
        sample_id="TEST-001",
        bracken_path=str(bracken_file),
        kreport_path=str(kreport_file),
        fastp_json=str(fastp_json_file),
    )
    assert report.method == "kraken2_bracken"
    assert report.qc.total_reads == 100000
    assert report.qc.classified_reads == 100000
    hits = {row.name for row in report.priority_hits}
    assert hits == {"Vibrio cholerae", "Vibrio parahaemolyticus", "Escherichia coli"}
    # sorted by fraction descending: Homo sapiens first
    assert report.taxa[0].name == "Homo sapiens"


def test_build_report_min_fraction_and_top(bracken_file: Path) -> None:
    report = build_report(
        sample_id="X",
        bracken_path=str(bracken_file),
        min_fraction=0.02,
        top=2,
    )
    assert [row.name for row in report.taxa] == ["Homo sapiens", "Vibrio cholerae"]


def test_build_report_requires_input() -> None:
    import pytest

    with pytest.raises(ValueError):
        build_report(sample_id="X")
