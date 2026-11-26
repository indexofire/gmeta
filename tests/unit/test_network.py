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
    species_kingdoms,
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
    # host taxa (Homo sapiens, 9606) are excluded before ranking
    pairs = top_species(parse_kreport(kreport_file), 3)
    assert [sp.name for sp, _ in pairs] == [
        "Vibrio cholerae",
        "Escherichia coli",
        "Vibrio parahaemolyticus",
    ]


def test_top_species_excludes_host_taxa(kreport_file: Path) -> None:
    pairs = top_species(parse_kreport(kreport_file), 10)
    assert all(sp.taxid != 9606 for sp, _ in pairs)
    assert all(sp.name != "Homo sapiens" for sp, _ in pairs)


VIRAL_KREPORT = """100.00\t0\t100000\tR\t1\troot
 40.00\t40000\t40000\tD\t10239\t  Viruses
  5.00\t5000\t5000\tS\t11320\t    Influenza A virus
 55.00\t55000\t1000\tD\t2\t  Bacteria
 25.00\t25000\t25000\tS\t662\t    Vibrio cholerae
  8.00\t8000\t8000\tS\t562\t    Escherichia coli
 40.00\t40000\t40000\tU\t0\tunclassified
"""


def test_kingdom_filter_excludes_viruses_by_default(tmp_path: Path) -> None:
    path = tmp_path / "viral.report"
    path.write_text(VIRAL_KREPORT)
    summary = parse_kreport(path)

    bacterial = build_rows(summary, "S1", top=10)
    assert "Influenza A virus" not in [row.species_latin for row in bacterial]
    assert [row.species_latin for row in bacterial] == ["Vibrio cholerae", "Escherichia coli"]

    with_viruses = build_rows(summary, "S1", top=10, kingdoms=frozenset({"bacteria", "viruses"}))
    assert "Influenza A virus" in [row.species_latin for row in with_viruses]

    everything = build_rows(summary, "S1", top=10, kingdoms=None)
    assert "Influenza A virus" in [row.species_latin for row in everything]


def test_species_kingdoms_tree(tmp_path: Path) -> None:
    path = tmp_path / "viral.report"
    path.write_text(VIRAL_KREPORT)
    kingdoms = species_kingdoms(parse_kreport(path))
    assert kingdoms[11320] == "viruses"
    assert kingdoms[662] == "bacteria"


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

    assert "Homo sapiens" not in by_latin  # host taxon excluded


def test_build_rows_top_limit(kreport_file: Path) -> None:
    rows = build_rows(parse_kreport(kreport_file), "TEST-1", top=2)
    assert [row.species_latin for row in rows] == ["Vibrio cholerae", "Escherichia coli"]


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
    assert ws.cell(row=5, column=1).value == "S2"  # new sample group (S1 has 3 rows)
    assert ws.cell(row=2, column=4).value == "30.00%"  # genus Vibrio clade 30%
    assert abs(ws.cell(row=2, column=7).value - 94.5350845526999) < 1e-9

    detail = wb[DETAIL_SHEET]
    assert detail.cell(row=2, column=4).value == "Vibrio cholerae"  # 种拉丁名
    assert all(cell.value != "Homo sapiens" for row in detail.iter_rows(min_row=2) for cell in row)


def test_split_by_sample(kreport_file: Path, tmp_path: Path) -> None:
    rows = build_rows(parse_kreport(kreport_file), "S1", top=2)
    rows += build_rows(parse_kreport(kreport_file), "S2", top=1)
    written = split_by_sample(rows, tmp_path / "result")
    assert sorted(p.name for p in written) == ["S1.xlsx", "S2.xlsx"]

    ws = load_workbook(tmp_path / "result" / "S1.xlsx").active
    assert ws.max_row == 3  # header + 2 rows
    assert ws.cell(row=2, column=1).value == "S1"
    assert ws.cell(row=3, column=1).value == "S1"  # single-sample file: always filled
