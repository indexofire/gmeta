"""HTML rendering via Jinja2 (the single source for both web and PDF)."""

from __future__ import annotations

from functools import lru_cache

from jinja2 import Environment, FunctionLoader, StrictUndefined

from gmeta.report.models import MetaReport

_TEMPLATE_NAME = "report.html.j2"

_METHOD_LABELS = {
    "kraken2_bracken": "kraken2 + bracken 物种丰度分析",
    "sylph_ani": "sylph ANI 物种丰度分析",
}


@lru_cache(maxsize=1)
def _load_template_source(name: str) -> str | None:
    if name != _TEMPLATE_NAME:
        return None
    from importlib import resources

    return resources.files("gmeta.templates").joinpath(name).read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FunctionLoader(_load_template_source),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _fmt_int(value: int | None) -> str:
    return f"{value:,}" if value is not None else "—"


def _fmt_pct(value: float | None) -> str:
    return f"{value * 100:.2f}%" if value is not None else "—"


def method_label(method: str) -> str:
    return _METHOD_LABELS.get(method, method)


def render_html(report: MetaReport) -> str:
    """Render the full HTML report (self-contained, no external assets)."""
    template = _env().get_template(_TEMPLATE_NAME)
    return template.render(
        report=report,
        fmt_int=_fmt_int,
        fmt_pct=_fmt_pct,
        method_label=method_label,
    )
