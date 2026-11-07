"""国家致病菌识别网（China CDC pathogen surveillance network）export format.

Target layout (template.xls sheet 混合样本):

    样本名称 | 属中文名 | 属序列数 | 属相对丰度 | 种中文名 | 种序列数 | 种基因组覆盖度 | 种相对丰度

One row per species (top-N by species fraction), the parent genus repeated on
every row; 样本名称 is only written on the first row of each sample group.
拉丁名 / TaxID / accession / 参考基因组 / depth 明细 live on a second review
sheet so nothing is lost while the submission sheet stays template-exact.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from gmeta.analysis.kraken2 import KreportRow, KreportSummary
from gmeta.analysis.profilers import AbundanceProfile, TaxonAbundance

NETWORK_SHEET = "混合样本"
DETAIL_SHEET = "审核明细"

NETWORK_COLUMNS = [
    "样本名称",
    "属中文名",
    "属序列数",
    "属相对丰度",
    "种中文名",
    "种序列数",
    "种基因组覆盖度",
    "种相对丰度",
]
DETAIL_COLUMNS = [
    "样本名称",
    "属拉丁名",
    "属中文名",
    "种拉丁名",
    "种中文名",
    "TaxID",
    "属序列数",
    "种序列数",
    "种相对丰度",
    "accession",
    "参考基因组",
    "参考基因组长度",
    "平均测序深度",
    "覆盖度1x(%)",
]

_HEADER_FILL = PatternFill("solid", fgColor="0F5C8C")
_HEADER_FONT = Font(color="FFFFFF", bold=True)


@dataclass
class NetworkRow:
    """One species row in the surveillance format (plus review extras)."""

    sample_id: str
    genus_latin: str
    genus_cn: str
    genus_reads: int
    genus_fraction: float
    species_latin: str
    species_cn: str
    species_reads: int
    species_fraction: float
    taxid: int
    accession: str | None = None
    reference: str | None = None
    reference_length: int | None = None
    mean_depth: float | None = None
    coverage_pct_1x: float | None = None  # 种基因组覆盖度, percent 0..100

    def network_cells(self, with_sample: bool = True) -> list[Any]:
        """The 8 template cells; blank 样本名称 on continuation rows."""
        return [
            self.sample_id if with_sample else None,
            self.genus_cn,
            self.genus_reads,
            format_percent(self.genus_fraction),
            self.species_cn,
            self.species_reads,
            self.coverage_pct_1x,
            format_percent(self.species_fraction),
        ]

    def detail_cells(self) -> list[Any]:
        return [
            self.sample_id,
            self.genus_latin,
            self.genus_cn,
            self.species_latin,
            self.species_cn,
            self.taxid,
            self.genus_reads,
            self.species_reads,
            format_percent(self.species_fraction),
            self.accession or "",
            self.reference or "",
            self.reference_length,
            round(self.mean_depth, 4) if self.mean_depth is not None else None,
            round(self.coverage_pct_1x, 4) if self.coverage_pct_1x is not None else None,
        ]


def format_percent(fraction: float) -> str:
    """0.4823 → '48.23%' (the template stores abundance as percent strings)."""
    return f"{fraction * 100:.2f}%"


# ---------------------------------------------------------------------------
# Chinese name lookup
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def _load_name_tables() -> tuple[dict[str, str], dict[str, str], dict[int, tuple[str, str]]]:
    """(species latin→cn, genus latin→cn, taxid→(genus_cn, species_cn))."""
    species: dict[str, str] = {}
    genus: dict[str, str] = {}
    by_taxid: dict[int, tuple[str, str]] = {}

    species_tsv = _DATA_DIR / "species_chinese_names.tsv"
    if species_tsv.is_file():
        with species_tsv.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                latin = (row.get("latin_name") or "").strip().lower()
                if latin:
                    species[latin] = (row.get("chinese_name") or "").strip()

    genus_tsv = _DATA_DIR / "genus_chinese_names.tsv"
    if genus_tsv.is_file():
        with genus_tsv.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                latin = (row.get("latin_name") or "").strip().lower()
                if latin:
                    genus[latin] = (row.get("chinese_name") or "").strip()

    taxid_csv = _DATA_DIR / "taxid_chinese_mapping.csv"
    if taxid_csv.is_file():
        with taxid_csv.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    taxid = int(row["TaxID"])
                except (KeyError, TypeError, ValueError):
                    continue
                by_taxid[taxid] = (
                    (row.get("属中文名") or "").strip(),
                    (row.get("种中文名") or "").strip(),
                )
    return species, genus, by_taxid


def chinese_species_name(latin: str, taxid: int | None = None) -> str:
    """TaxID table first (most precise), latin TSV second, latin itself last."""
    _species, _genus, by_taxid = _load_name_tables()
    if taxid is not None and taxid in by_taxid and by_taxid[taxid][1]:
        return by_taxid[taxid][1]
    return _species.get(latin.strip().lower(), latin)


def chinese_genus_name(latin: str, species_taxid: int | None = None) -> str:
    _species, genus_table, by_taxid = _load_name_tables()
    if species_taxid is not None and species_taxid in by_taxid and by_taxid[species_taxid][0]:
        return by_taxid[species_taxid][0]
    return genus_table.get(latin.strip().lower(), latin)


# ---------------------------------------------------------------------------
# kreport tree → species rows
# ---------------------------------------------------------------------------


def pair_species_with_genus(
    summary: KreportSummary,
) -> list[tuple[KreportRow, KreportRow | None]]:
    """Species rows with their nearest genus ancestor (indentation tree)."""
    stack: list[KreportRow] = []
    pairs: list[tuple[KreportRow, KreportRow | None]] = []
    for row in summary.rows:
        while stack and stack[-1].depth >= row.depth:
            stack.pop()
        if row.rank == "species":
            genus = next((a for a in reversed(stack) if a.rank == "genus"), None)
            pairs.append((row, genus))
        stack.append(row)
    return pairs


def top_species(summary: KreportSummary, top: int) -> list[tuple[KreportRow, KreportRow | None]]:
    """Top-N (species, genus) pairs by species read count."""
    pairs = sorted(pair_species_with_genus(summary), key=lambda p: p[0].reads_total, reverse=True)
    return pairs[:top]


def resolve_references(
    pairs: Sequence[tuple[KreportRow, KreportRow | None]],
    manifest: dict[int, Any] | None,
    ref_dir: str | Path | None,
) -> tuple[dict[int, tuple[str, Path]], list[int]]:
    """Map species taxids of ``pairs`` to reference FASTAs.

    Returns ``(references, missing_taxids)`` where references maps
    taxid → (accession, fasta path).
    """
    from gmeta.analysis.coverage import resolve_reference

    references: dict[int, tuple[str, Path]] = {}
    missing: list[int] = []
    for species, _genus in pairs:
        if species.taxid in references or species.taxid in missing:
            continue
        entry, path = resolve_reference(species.taxid, manifest, ref_dir)
        if path is not None:
            references[species.taxid] = (entry.accession if entry else "", path)
        else:
            missing.append(species.taxid)
    return references, missing


def build_rows(
    summary: KreportSummary,
    sample_id: str,
    top: int = 10,
    references: dict[int, tuple[str, Path]] | None = None,
) -> list[NetworkRow]:
    """Top-N species rows from a kraken2 kreport tree, ready for coverage filling.

    ``references`` maps species taxid → (accession, fasta path) so rows carry
    the review-sheet extras; coverage numbers are filled later.
    """
    refs = references or {}
    pairs = top_species(summary, top)

    rows: list[NetworkRow] = []
    for species, genus in pairs:
        latin = species.name
        if genus is None:
            # genus-level gap in the report tree: fall back to the first word
            # with the species' own counts so the row is still reportable.
            genus_latin = latin.split()[0] if latin.split() else latin
            genus_reads, genus_fraction = species.reads_total, species.fraction
        else:
            genus_latin = genus.name
            genus_reads, genus_fraction = genus.reads_total, genus.fraction
        accession, reference = refs.get(species.taxid, (None, None))
        rows.append(
            NetworkRow(
                sample_id=sample_id,
                genus_latin=genus_latin,
                genus_cn=chinese_genus_name(genus_latin, species.taxid),
                genus_reads=genus_reads,
                genus_fraction=genus_fraction,
                species_latin=latin,
                species_cn=chinese_species_name(latin, species.taxid),
                species_reads=species.reads_total,
                species_fraction=species.fraction,
                taxid=species.taxid,
                accession=accession,
                reference=str(reference) if reference else None,
            )
        )
    return rows


def resolve_taxids(
    taxids: Sequence[int],
    manifest: dict[int, Any] | None,
    ref_dir: str | Path | None,
) -> tuple[dict[int, tuple[str, Path]], list[int]]:
    """Resolve reference genomes for explicit taxids (table-based profilers)."""
    from gmeta.analysis.coverage import resolve_reference

    references: dict[int, tuple[str, Path]] = {}
    missing: list[int] = []
    for taxid in taxids:
        if not taxid or taxid in references or taxid in missing:
            continue
        entry, path = resolve_reference(taxid, manifest, ref_dir)
        if path is not None:
            references[taxid] = (entry.accession if entry else "", path)
        else:
            missing.append(taxid)
    return references, missing


def profile_to_network_rows(
    path: str | Path,
    sample_id: str,
    top: int = 10,
    manifest: dict[int, Any] | None = None,
    ref_dir: str | Path | None = None,
    profiler: str = "auto",
    kaiju_genus: str | Path | None = None,
) -> tuple[list[NetworkRow], list[int], str]:
    """Any supported profiler output → 识别网 rows.

    Returns ``(rows, missing_reference_taxids, detected_profiler)``. kraken2
    kreports keep the exact tree-based path (real genus clade counts); every
    other profiler goes through the AbundanceProfile adapter.
    """
    from gmeta.analysis import profilers as P
    from gmeta.analysis.kraken2 import parse_kreport

    detected = profiler if profiler != "auto" else P.detect_profiler(path)

    if detected == "kraken2":
        summary = parse_kreport(path)
        references, missing = resolve_references(top_species(summary, top), manifest, ref_dir)
        return build_rows(summary, sample_id, top, references), missing, detected

    if detected == "bracken":
        from gmeta.analysis.kraken2 import parse_bracken

        profile = AbundanceProfile(
            method="bracken",
            species=[
                TaxonAbundance(
                    name=row["name"],
                    taxid=row.get("taxid"),
                    reads=row.get("reads"),
                    fraction=row["fraction"],
                )
                for row in parse_bracken(path)
            ],
        )
    elif detected == P.CENTRIFUGE:
        profile = P.parse_centrifuge_report(path)
    elif detected == P.KAIJU:
        profile = P.parse_kaiju_table(path)
        if kaiju_genus:
            P.attach_kaiju_genus(profile, kaiju_genus)
    elif detected == P.METAPHLAN:
        profile = P.parse_metaphlan_profile(path)
    elif detected == P.KMCP:
        profile = P.parse_kmcp_profile(path)
    elif detected == "sylph":
        from gmeta.analysis import parse_profile as parse_sylph_profile

        profile = AbundanceProfile(
            method="sylph",
            species=[
                TaxonAbundance(name=row["name"], fraction=row["abundance"])
                for row in parse_sylph_profile(path)
            ],
        )
    else:
        raise ValueError(f"unsupported profiler: {detected!r} ({path})")

    top_taxids = [t.taxid for t in profile.species_sorted()[:top] if t.taxid]
    references, missing = resolve_taxids(top_taxids, manifest, ref_dir)
    return build_rows_from_profile(profile, sample_id, top, references), missing, detected


def build_rows_from_profile(
    profile: AbundanceProfile,
    sample_id: str,
    top: int = 10,
    references: dict[int, tuple[str, Path]] | None = None,
) -> list[NetworkRow]:
    """识别网 rows from any normalised AbundanceProfile (centrifuge/kaiju/
    metaphlan/kmcp/bracken-only).

    Genus numbers come from the profile's own genus rows when present
    (centrifuge, metaphlan, or a kaiju genus table); otherwise they are
    aggregated from the profile's species rows of that genus — the honest
    estimate table-based profilers can offer.
    """
    refs = references or {}
    genus_table = profile.genus_by_name()

    # aggregate species by genus latin (first word) for the fallback path
    genus_latin_of: dict[str, str] = {}
    genus_agg: dict[str, list[float]] = {}
    for taxon in profile.species:
        hint = profile._genus_hints.get(taxon.name.lower())
        genus_latin = hint or taxon.name.split()[0]
        genus_latin_of[taxon.name.lower()] = genus_latin
        stats = genus_agg.setdefault(genus_latin.lower(), [0, 0.0])
        stats[0] += taxon.reads or 0
        stats[1] += taxon.fraction

    rows: list[NetworkRow] = []
    for taxon in profile.species_sorted()[:top]:
        genus_latin = genus_latin_of[taxon.name.lower()]
        genus_row = genus_table.get(genus_latin.lower())
        if genus_row is not None:
            genus_reads = genus_row.reads or 0
            genus_fraction = genus_row.fraction
        else:
            agg_reads, agg_fraction = genus_agg[genus_latin.lower()]
            genus_reads = int(agg_reads)
            genus_fraction = agg_fraction
        accession, reference = refs.get(taxon.taxid or -1, (None, None))
        rows.append(
            NetworkRow(
                sample_id=sample_id,
                genus_latin=genus_latin,
                genus_cn=chinese_genus_name(genus_latin, taxon.taxid),
                genus_reads=genus_reads,
                genus_fraction=genus_fraction,
                species_latin=taxon.name,
                species_cn=chinese_species_name(taxon.name, taxon.taxid),
                species_reads=taxon.reads if taxon.reads is not None else 0,
                species_fraction=taxon.fraction,
                taxid=taxon.taxid or 0,
                accession=accession,
                reference=str(reference) if reference else None,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Excel output
# ---------------------------------------------------------------------------


def _style_header(ws, ncols: int) -> None:
    for col in range(1, ncols + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")


def _write_network_sheet(ws, rows: Sequence[NetworkRow], *, always_sample: bool = False) -> None:
    """Write the 8-column sheet.

    ``always_sample`` fills 样本名称 on every row (per-sample workbooks);
    otherwise only the first row of each sample group carries it (the
    multi-sample template style).
    """
    ws.append(NETWORK_COLUMNS)
    _style_header(ws, len(NETWORK_COLUMNS))
    current_sample: str | None = None
    for row in rows:
        with_sample = always_sample or row.sample_id != current_sample
        ws.append(row.network_cells(with_sample=with_sample))
        current_sample = row.sample_id
    widths = [16, 24, 12, 12, 24, 12, 16, 12]
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width


def write_network_xlsx(rows: Sequence[NetworkRow], path: str | Path) -> Path:
    """Submission workbook: 混合样本 sheet + 审核明细 review sheet."""
    wb = Workbook()
    _write_network_sheet(wb.active, rows)
    wb.active.title = NETWORK_SHEET

    detail = wb.create_sheet(DETAIL_SHEET)
    detail.append(DETAIL_COLUMNS)
    _style_header(detail, len(DETAIL_COLUMNS))
    for row in rows:
        detail.append(row.detail_cells())
    detail.freeze_panes = "A2"
    for i, width in enumerate([16, 20, 22, 26, 24, 10, 12, 12, 12, 16, 52, 14, 12, 12], start=1):
        detail.column_dimensions[get_column_letter(i)].width = width

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def split_by_sample(rows: Sequence[NetworkRow], out_dir: str | Path) -> list[Path]:
    """One single-sheet workbook per sample (识别网 per-sample submission)."""
    by_sample: dict[str, list[NetworkRow]] = {}
    for row in rows:
        by_sample.setdefault(row.sample_id, []).append(row)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for sample_id, sample_rows in by_sample.items():
        target = out / f"{sample_id}.xlsx"
        wb = Workbook()
        _write_network_sheet(wb.active, sample_rows, always_sample=True)
        wb.save(target)
        written.append(target)
    return written


def write_coverage_details(
    rows: Sequence[NetworkRow], path: str | Path
) -> Path:  # pragma: no cover — convenience TSV mirroring the old workflow
    """Plain TSV with every coverage metric (like the old coverage_details.tsv)."""
    import json

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        fh.write("\t".join(DETAIL_COLUMNS) + "\n")
        for row in rows:
            cells = []
            for cell in row.detail_cells():
                if cell is None:
                    cells.append("")
                elif isinstance(cell, float):
                    cells.append(json.dumps(cell))
                else:
                    cells.append(str(cell))
            fh.write("\t".join(cells) + "\n")
    return out
