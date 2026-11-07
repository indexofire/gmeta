"""Report assembly and multi-format output.

``write_report`` dispatches on the output extension so callers never pick a
renderer by hand: ``.html``/``.htm`` → HTML, ``.xlsx`` → Excel, ``.pdf`` →
PDF, ``.json`` (and anything else) → the model dump.
"""

from __future__ import annotations

from pathlib import Path

from gmeta.report.excel import write_excel
from gmeta.report.models import (
    MetaReport,
    QcSection,
    SampleInfo,
    TaxonRow,
    build_report,
)
from gmeta.report.pdf import write_pdf
from gmeta.report.render import render_html

__all__ = [
    "MetaReport",
    "QcSection",
    "SampleInfo",
    "TaxonRow",
    "build_report",
    "render_html",
    "write_excel",
    "write_pdf",
    "write_report",
]


def write_report(report: MetaReport, output: str | Path) -> Path:
    """Write one report file, choosing the renderer from the extension."""
    out = Path(output)
    suffix = out.suffix.lower()
    if suffix in (".html", ".htm"):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_html(report), encoding="utf-8")
    elif suffix == ".xlsx":
        write_excel(report, out)
    elif suffix == ".pdf":
        write_pdf(report, out)
    else:  # .json and default
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return out
