"""国家致病菌识别网 export: tree pairing, Chinese names, workbook output."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from gmeta.analysis.kraken2 import parse_kreport
from gmeta.report.network import (
    DETAIL_SHEET,
    NETWORK_SHEET,
    build_rows,
    chinese_genus_name,
    chinese_species_name,
    format_percent,
    pair_species_with_genus,
    split_by_sample,
    top_species,
    write_network_xlsx,
)


def test_pair_species_with_genus(kreport_file: Path) -> None:
    summary = parse_kreport(kreport_file)
    pairs = pair_species_with_genus(summary)
    by_species = {sp.name: (gn.name if gn else None) for sp, gn in pairs}
    assert by_species["Vibrio cholerae"] == "Vibrio"
    assert by_species["Vibrio parahaemolyticus"] == "Vibrio"
    assert by_species["Homo sapiens"] is None  # no genus ancestor in fixture
    assert "Vibrio cholerae O1" not in by_species  # S1 rows are not species


def test_top_species_orders_by_reads(kreport_file: Path) -> None:
    pairs = top_species(parse_kreport(kreport_file), 3)
    assert [sp.name for sp, _ in pairs] == [
        "Homo sapiens",
        "Vibrio cholerae",
        "Escherichia coli",
    ]


def test_chinese_species_name_lookup() -> None:
    assert chinese_species_name("Escherichia coli", 562) == "大肠埃希氏菌"  # taxid table
    assert chinese_species_name("Vibrio cholerae", 662) == "Vibrio cholerae"  # fallback


def test_chinese_genus_name_lookup() -> None:
    assert chinese_genus_name("Vibrio", None) == "弧菌属"
    assert chinese_genus_name("Escherichia", 562) == "埃希氏菌属"  # taxid table
    assert chinese_genus_name("Homo", None) == "Homo"  # fallback


def test_format_percent() -> None:
    assert format_percent(0.4823) == "48.23%"
    assert format_percent(0.005) == "0.50%"


def test_build_rows_genus_fallback_and_names(kreport_file: Path) -> None:
    summary = parse_kreport(kreport_file)
    rows = build_rows(summary, "TEST-1", top=10)
    by_latin = {row.species_latin: row for row in rows}

    ecoli = by_latin["Escherichia coli"]
    assert ecoli.species_cn == "大肠埃希氏菌"
    assert ecoli.genus_cn == "埃希氏菌属"
    assert ecoli.genus_latin == "Escherichia"

    cholera = by_latin["Vibrio cholerae"]
    assert cholera.genus_cn == "弧菌属"
    assert cholera.species_cn == "Vibrio cholerae"  # not in the mapping tables
    assert cholera.genus_reads == 29500
    assert cholera.species_reads == 25000

    homo = by_latin["Homo sapiens"]
    assert homo.genus_latin == "Homo"  # first-word fallback
    assert homo.genus_reads == homo.species_reads


def test_build_rows_top_limit(kreport_file: Path) -> None:
    rows = build_rows(parse_kreport(kreport_file), "TEST-1", top=2)
    assert [row.species_latin for row in rows] == ["Homo sapiens", "Vibrio cholerae"]


def test_write_network_xlsx(kreport_file: Path, tmp_path: Path) -> None:
    rows = build_rows(parse_kreport(kreport_file), "S1", top=10)
    rows += build_rows(parse_kreport(kreport_file), "S2", top=2)
    # simulate a coverage number on one row
    rows[0].coverage_pct_1x = 94.5350845526999
    out = write_network_xlsx(rows, tmp_path / "上报.xlsx")

    wb = load_workbook(out)
    assert wb.sheetnames == [NETWORK_SHEET, DETAIL_SHEET]
    ws = wb[NETWORK_SHEET]
    header = [c.value for c in ws[1]]
    assert header == [
        "样本名称",
        "属中文名",
        "属序列数",
        "属相对丰度",
        "种中文名",
        "种序列数",
        "种基因组覆盖度",
        "种相对丰度",
    ]
    # first data row carries the sample id, continuation rows do not
    assert ws.cell(row=2, column=1).value == "S1"
    assert ws.cell(row=3, column=1).value is None
    assert ws.cell(row=6, column=1).value == "S2"  # new sample group
    assert ws.cell(row=2, column=4).value == "40.00%"
    assert abs(ws.cell(row=2, column=7).value - 94.5350845526999) < 1e-9

    detail = wb[DETAIL_SHEET]
    assert detail.cell(row=2, column=4).value == "Homo sapiens"  # 种拉丁名


def test_split_by_sample(kreport_file: Path, tmp_path: Path) -> None:
    rows = build_rows(parse_kreport(kreport_file), "S1", top=2)
    rows += build_rows(parse_kreport(kreport_file), "S2", top=1)
    written = split_by_sample(rows, tmp_path / "result")
    assert sorted(p.name for p in written) == ["S1.xlsx", "S2.xlsx"]

    ws = load_workbook(tmp_path / "result" / "S1.xlsx").active
    assert ws.max_row == 3  # header + 2 rows
    assert ws.cell(row=2, column=1).value == "S1"
    assert ws.cell(row=3, column=1).value == "S1"  # single-sample file: always filled
