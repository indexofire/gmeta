"""Excel report via openpyxl — the data-exchange format for network reporting."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from gmeta.report.models import MetaReport

_HEADER_FILL = PatternFill("solid", fgColor="0F5C8C")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_PRIORITY_FILL = PatternFill("solid", fgColor="FDF3EC")


def _style_header(ws, row: int, ncols: int) -> None:
    for col in range(1, ncols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")


def write_excel(report: MetaReport, path: str | Path) -> Path:
    """Two sheets: 检测概览 (overview) + 物种检出 (taxon table)."""
    wb = Workbook()

    overview = wb.active
    overview.title = "检测概览"
    overview.append(["项目", "内容"])
    _style_header(overview, 1, 2)
    rows = [
        ("样本编号", report.sample.sample_id),
        ("样本类型", report.sample.sample_type or ""),
        ("测序平台", report.sample.platform or ""),
        ("测序日期", report.sample.sequencing_date or ""),
        ("检测单位", report.sample.lab or ""),
        ("检测人员", report.sample.operator or ""),
        ("分析流程", report.method),
        ("参考数据库", report.database or ""),
        ("原始读段数", report.qc.total_reads),
        ("质控后读段数", report.qc.clean_reads),
        ("原始数据量 (bp)", report.qc.total_bases),
        ("质控后数据量 (bp)", report.qc.clean_bases),
        ("Q30 比例", report.qc.q30_rate),
        ("宿主读段占比", report.qc.host_rate),
        ("分类读段数", report.qc.classified_reads),
        ("分类比例", report.qc.classified_fraction),
        ("重点病原检出数", len(report.priority_hits)),
        ("报告生成时间", report.generated_at),
        ("gmeta 版本", report.tool_version),
    ]
    for label, value in rows:
        overview.append([label, value])
    overview.column_dimensions["A"].width = 22
    overview.column_dimensions["B"].width = 46

    taxa = wb.create_sheet("物种检出")
    header = ["序号", "物种", "TaxID", "分类等级", "读段数", "丰度", "ANI", "置信度", "重点标注"]
    taxa.append(header)
    _style_header(taxa, 1, len(header))
    for i, row in enumerate(report.taxa, start=1):
        taxa.append(
            [
                i,
                row.name,
                row.taxid,
                row.rank,
                row.reads,
                row.fraction,
                row.ani,
                row.confidence,
                row.priority_category or "",
            ]
        )
        if row.priority:
            for col in range(1, len(header) + 1):
                taxa.cell(row=i + 1, column=col).fill = _PRIORITY_FILL
    taxa.freeze_panes = "A2"
    for col, width in enumerate([6, 42, 12, 10, 12, 10, 10, 10, 30], start=1):
        taxa.column_dimensions[get_column_letter(col)].width = width

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
