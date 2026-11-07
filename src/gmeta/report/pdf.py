"""PDF rendering via WeasyPrint — same template as the HTML report."""

from __future__ import annotations

from pathlib import Path

from gmeta.report.models import MetaReport
from gmeta.report.render import render_html


def write_pdf(report: MetaReport, path: str | Path) -> Path:
    """Render the HTML report to PDF (requires a system pango, pixi provides it)."""
    from weasyprint import HTML  # deferred: heavy import, optional in tests

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=render_html(report), encoding="utf-8").write_pdf(out)
    return out
