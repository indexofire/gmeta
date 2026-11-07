"""Multi-format report rendering."""

from __future__ import annotations

from pathlib import Path

from gmeta.report import build_report, render_html, write_report
from gmeta.report.excel import write_excel
from gmeta.report.models import SampleInfo


def _report(bracken_file: Path, fastp_json_file: Path):
    return build_report(
        sample_id="TEST-001",
        bracken_path=str(bracken_file),
        fastp_json=str(fastp_json_file),
        sample=SampleInfo(
            sample_id="TEST-001", sample_type="粪便", platform="MGI-2000", lab="省疾控中心"
        ),
    )


def test_render_html_contains_sections(bracken_file: Path, fastp_json_file: Path) -> None:
    html = render_html(_report(bracken_file, fastp_json_file))
    assert "mNGS" in html
    assert "TEST-001" in html
    assert "霍乱弧菌" in html  # priority annotation surfaces in the report
    assert "Vibrio cholerae" in html
    assert "25.00%" in html  # fraction formatting


def test_render_html_sylph_layout(bracken_file: Path) -> None:
    # reuse bracken fixture through the kreport fallback path is not sylph;
    # instead render a sylph-shaped report by hand
    from gmeta.report.models import MetaReport, QcSection, SampleInfo, TaxonRow

    report = MetaReport(
        sample=SampleInfo(sample_id="SY-1"),
        method="sylph_ani",
        qc=QcSection(),
        taxa=[TaxonRow(name="Yersinia pestis", fraction=0.3, ani=96.5, confidence="high")],
    )
    from gmeta.report.priority import annotate

    annotate(report.taxa)
    html = render_html(report)
    assert "ANI (%)" in html
    assert "96.50" in html
    assert "鼠疫耶尔森菌" in html


def test_write_report_json(bracken_file: Path, fastp_json_file: Path, tmp_path: Path) -> None:
    out = write_report(_report(bracken_file, fastp_json_file), tmp_path / "r.json")
    data = out.read_text()
    assert '"sample_id": "TEST-001"' in data


def test_write_report_html(bracken_file: Path, fastp_json_file: Path, tmp_path: Path) -> None:
    out = write_report(_report(bracken_file, fastp_json_file), tmp_path / "r.html")
    assert "<!DOCTYPE html>" in out.read_text()


def test_write_excel(bracken_file: Path, fastp_json_file: Path, tmp_path: Path) -> None:
    out: Path = write_excel(_report(bracken_file, fastp_json_file), tmp_path / "r.xlsx")
    assert out.is_file() and out.stat().st_size > 1000
    from openpyxl import load_workbook

    wb = load_workbook(out)
    assert wb.sheetnames == ["检测概览", "物种检出"]
    ws = wb["物种检出"]
    assert ws.cell(row=1, column=2).value == "物种"
    assert ws.cell(row=2, column=2).value == "Homo sapiens"
