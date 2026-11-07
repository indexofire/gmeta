"""Report data model (pydantic v2) for surveillance/outbreak mNGS reports.

The model is format-neutral: profilers fill it, renderers (HTML/Excel/PDF/
JSON) consume it. Field names are English (stable JSON keys); display labels
live in the templates so Chinese wording can change without a schema bump.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from gmeta import __version__
from gmeta.analysis import (
    HostRemovalStats,
    KreportSummary,
    QcMetrics,
    parse_bracken,
    parse_fastp_json,
    parse_kreport,
)


class SampleInfo(BaseModel):
    sample_id: str
    sample_type: str | None = None  # 血清/脑脊液/粪便/拭子…
    platform: str | None = None  # e.g. MGI-2000, NextSeq
    sequencing_date: str | None = None  # ISO date string, display only
    lab: str | None = None
    operator: str | None = None


class QcSection(BaseModel):
    total_reads: int | None = None
    clean_reads: int | None = None
    total_bases: int | None = None
    clean_bases: int | None = None
    q30_rate: float | None = None
    duplication_rate: float | None = None
    host_reads: int | None = None
    host_rate: float | None = None
    classified_reads: int | None = None
    classified_fraction: float | None = None

    @classmethod
    def from_metrics(
        cls,
        qc: QcMetrics | None = None,
        host: HostRemovalStats | None = None,
        kreport: KreportSummary | None = None,
    ) -> QcSection:
        return cls(
            **(qc.to_dict() if qc else {}),
            host_reads=host.host_reads if host else None,
            host_rate=host.host_rate if host else None,
            classified_reads=kreport.classified_reads if kreport else None,
            classified_fraction=round(kreport.classified_fraction, 6) if kreport else None,
        )


class TaxonRow(BaseModel):
    name: str
    taxid: int | None = None
    rank: str = "species"
    reads: int | None = None  # bracken estimated reads (kraken2 method)
    fraction: float  # 0..1
    ani: float | None = None  # sylph method
    confidence: str = "low"  # high / medium / low
    priority: bool = False
    priority_category: str | None = None  # 肠道/呼吸道/人畜共患病…

    def to_table_row(self) -> list[Any]:
        return [
            self.name,
            self.taxid,
            self.rank,
            self.reads,
            self.fraction,
            self.ani,
            self.confidence,
            self.priority_category or "",
        ]


class MetaReport(BaseModel):
    schema_version: int = 1
    tool: str = "gmeta"
    tool_version: str = Field(default_factory=lambda: __version__)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    sample: SampleInfo
    method: str = "kraken2_bracken"  # kraken2_bracken / sylph_ani
    database: str | None = None
    qc: QcSection = Field(default_factory=QcSection)
    taxa: list[TaxonRow] = Field(default_factory=list)
    n_species: int = 0

    @property
    def priority_hits(self) -> list[TaxonRow]:
        return [row for row in self.taxa if row.priority]


def build_report(
    sample_id: str,
    bracken_path: str | None = None,
    kreport_path: str | None = None,
    fastp_json: str | None = None,
    sylph_profile: str | None = None,
    centrifuge_report: str | None = None,
    kaiju_table: str | None = None,
    kaiju_genus_table: str | None = None,
    metaphlan_profile: str | None = None,
    kmcp_profile: str | None = None,
    sample: SampleInfo | None = None,
    database: str | None = None,
    top: int = 50,
    min_fraction: float = 0.0,
    annotate_priority: bool = True,
) -> MetaReport:
    """Assemble a MetaReport from any mix of existing result files.

    Exactly one profiler source (kraken2 kreport/bracken, sylph, centrifuge,
    kaiju, metaphlan or kmcp) is required; QC inputs are optional and merged
    when present.
    """
    from gmeta.report.priority import annotate

    qc = QcSection.from_metrics(
        qc=parse_fastp_json(fastp_json) if fastp_json else None,
        kreport=parse_kreport(kreport_path) if kreport_path else None,
    )

    if bracken_path or kreport_path:
        species = (
            parse_bracken(bracken_path)
            if bracken_path
            else _species_from_kreport(parse_kreport(kreport_path))
        )
        method = "kraken2_bracken"
        rows = [
            TaxonRow(
                name=row["name"],
                taxid=row.get("taxid"),
                reads=row.get("reads"),
                fraction=row["fraction"],
                confidence=row.get("confidence", "low"),
            )
            for row in species
        ]
    elif sylph_profile:
        from gmeta.analysis import parse_profile as parse_sylph_profile

        species = parse_sylph_profile(sylph_profile)
        method = "sylph_ani"
        rows = [
            TaxonRow(
                name=row["name"],
                fraction=row["abundance"],
                ani=row.get("ani"),
                confidence=row.get("confidence", "low"),
            )
            for row in species
        ]
    elif centrifuge_report or kaiju_table or metaphlan_profile or kmcp_profile:
        from gmeta.analysis import profilers

        if centrifuge_report:
            profile = profilers.parse_centrifuge_report(centrifuge_report)
        elif kaiju_table:
            profile = profilers.parse_kaiju_table(kaiju_table)
            if kaiju_genus_table:
                profilers.attach_kaiju_genus(profile, kaiju_genus_table)
        elif metaphlan_profile:
            profile = profilers.parse_metaphlan_profile(metaphlan_profile)
        else:
            profile = profilers.parse_kmcp_profile(kmcp_profile)  # type: ignore[arg-type]
        method = profile.method
        rows = [
            TaxonRow(
                name=taxon.name,
                taxid=taxon.taxid,
                reads=taxon.reads,
                fraction=taxon.fraction,
                confidence=_fraction_confidence(taxon.fraction),
            )
            for taxon in profile.species_sorted()
        ]
    else:
        raise ValueError(
            "need a profiler result (--bracken/--kreport/--sylph-profile/"
            "--centrifuge/--kaiju/--metaphlan/--kmcp)"
        )

    if annotate_priority:
        rows = annotate(rows)

    rows = [row for row in rows if row.fraction >= min_fraction][:top]
    return MetaReport(
        sample=sample or SampleInfo(sample_id=sample_id),
        method=method,
        database=database,
        qc=qc,
        taxa=rows,
        n_species=len(rows),
    )


def _fraction_confidence(fraction: float) -> str:
    """Abundance bands shared with the kraken2/bracken path (10% / 1%)."""
    if fraction >= 0.10:
        return "high"
    if fraction >= 0.01:
        return "medium"
    return "low"


def _species_from_kreport(summary: KreportSummary) -> list[dict[str, Any]]:
    """Species-level fallback when only a kreport (no bracken output) exists."""
    return [
        {
            "name": row.name,
            "taxid": row.taxid,
            "reads": row.reads_total,
            "fraction": row.fraction,
            "confidence": "low",  # no abundance re-estimation happened
        }
        for row in summary.at_rank("species")
    ]
