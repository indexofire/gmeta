"""Parsers for third-party mNGS profilers: Centrifuge, Kaiju, MetaPhlAn, KMCP.

Parsing-and-import layer only (no executors): profiles are produced upstream
and normalised into :class:`AbundanceProfile` — species rows plus optional
genus rows — which feeds both the report model and the 识别网 exporter.

Format references:
    centrifuge --report-file : name, taxID, taxRank, genomeSize, numReads,
                               numUniqueReads, abundance (tab-separated, no header)
    kaiju2table             : file, percent, reads, taxon_id, taxon_name
                               (taxon_name is a "; "-joined lineage when -l
                               lists multiple ranks)
    metaphlan profile       : "#clade_name  NCBI_tax_id  relative_abundance
                               [additional_species]" rows k__…/g__…/s__…
    kmcp profile            : 17 columns led by ref, percentage, …, reads,
                               ureads, …, taxid, [rank], [taxname] …
                               (reference-level rows, aggregated here by taxid)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

CENTRIFUGE = "centrifuge"
KAIJU = "kaiju"
METAPHLAN = "metaphlan"
KMCP = "kmcp"

_KRANKS = frozenset({"R", "U", "D", "K", "P", "C", "O", "F", "G", "S", "-"})

# centrifuge native report taxRank values (report has no header line)
_CF_RANKS = frozenset(
    {
        "superkingdom",
        "phylum",
        "class",
        "order",
        "family",
        "genus",
        "species",
        "strain",
        "subspecies",
        "no rank",
    }
)


@dataclass
class TaxonAbundance:
    """One abundance row at one rank."""

    name: str  # latin name at its rank
    taxid: int | None = None
    reads: int | None = None
    fraction: float = 0.0  # 0..1


@dataclass
class AbundanceProfile:
    """Normalised profiler output: species rows + optional genus rows."""

    method: str
    species: list[TaxonAbundance] = field(default_factory=list)
    genus: list[TaxonAbundance] = field(default_factory=list)
    total_reads: int | None = None
    # kaiju lineage hints: species latin (lower) → genus latin, used by the
    # 识别网 adapter when no genus table was supplied
    _genus_hints: dict[str, str] = field(default_factory=dict)

    def species_sorted(self) -> list[TaxonAbundance]:
        key = lambda t: t.reads if t.reads is not None else t.fraction * 1e9  # noqa: E731
        return sorted(self.species, key=key, reverse=True)

    def genus_by_name(self) -> dict[str, TaxonAbundance]:
        return {g.name.lower(): g for g in self.genus}


def _read_lines(path: str | Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        rows.append(line.split("\t"))
    return rows


def _to_int(value: str | None) -> int | None:
    try:
        return int(float(value)) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _to_float(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _normalise_fractions(
    rows: list[TaxonAbundance], explicit: list[float | None]
) -> list[TaxonAbundance]:
    """Trust the tool's own abundance column; recompute from reads only when
    it is missing.

    Explicit values may be percentages (kaiju, kmcp, metaphlan: 0..100) or
    fractions (centrifuge abundance: 0..1); the scale is inferred from the
    column sum (a percent column sums towards 100, a fraction column ≤1).
    """
    known = [value for value in explicit if value is not None]
    percent_scale = sum(known) > 1.5 if known else False
    for row, value in zip(rows, explicit, strict=True):
        if value is not None:
            row.fraction = value / 100.0 if percent_scale else value
    total = sum(row.reads for row in rows if row.reads is not None)
    for row in rows:
        if row.fraction == 0.0 and row.reads is not None and total:
            row.fraction = row.reads / total
    return rows


# ---------------------------------------------------------------------------
# Centrifuge (native --report-file)
# ---------------------------------------------------------------------------


def parse_centrifuge_report(path: str | Path) -> AbundanceProfile:
    """centrifuge native report → species + genus abundance rows.

    ``numReads`` is the clade read count at that rank; fractions are
    recomputed from reads so they stay consistent within the profile.
    """
    species: list[TaxonAbundance] = []
    genus: list[TaxonAbundance] = []
    sp_fracs: list[float | None] = []
    gn_fracs: list[float | None] = []
    for cols in _read_lines(path):
        if len(cols) < 6 or cols[0].startswith("name"):
            continue
        name, taxid, rank, _gsize, num_reads, _uniq, abundance = cols[:7]
        taxon = TaxonAbundance(
            name=name.strip(),
            taxid=_to_int(taxid),
            reads=_to_int(num_reads),
        )
        if rank == "species":
            species.append(taxon)
            sp_fracs.append(_to_float(abundance))
        elif rank == "genus":
            genus.append(taxon)
            gn_fracs.append(_to_float(abundance))
    return AbundanceProfile(
        method=CENTRIFUGE,
        species=_normalise_fractions(species, sp_fracs),
        genus=_normalise_fractions(genus, gn_fracs),
        total_reads=sum(r.reads or 0 for r in species),
    )


# ---------------------------------------------------------------------------
# Kaiju (kaiju2table)
# ---------------------------------------------------------------------------


def parse_kaiju_table(path: str | Path) -> AbundanceProfile:
    """kaiju2table output → abundance rows at the table's rank.

    kaiju2table is run per rank; pass the species table as the profile and
    (optionally) the genus table via :func:`attach_kaiju_genus`. When
    ``taxon_name`` carries the full lineage, the last segment is the taxon
    and the second-to-last its genus.
    """
    rows: list[TaxonAbundance] = []
    fracs: list[float | None] = []
    genus_seen: list[str | None] = []
    for cols in _read_lines(path):
        if len(cols) < 5 or cols[0] in ("file",) or cols[0].startswith("#"):
            continue
        _file, _percent, reads, taxon_id, taxon_name = cols[:5]
        segments = [seg.strip() for seg in taxon_name.split(";")]
        name = segments[-1]
        genus_seen.append(segments[-2] if len(segments) >= 2 else None)
        rows.append(TaxonAbundance(name=name, taxid=_to_int(taxon_id), reads=_to_int(reads)))
        fracs.append(_to_float(cols[1]))
    return AbundanceProfile(
        method=KAIJU,
        species=_normalise_fractions(rows, fracs),
        genus=[],
        total_reads=sum(r.reads or 0 for r in rows),
        # genus lineage hints ride along for the 识别网 adapter
        _genus_hints={r.name.lower(): g for r, g in zip(rows, genus_seen, strict=True) if g},
    )


def attach_kaiju_genus(profile: AbundanceProfile, genus_table: str | Path) -> AbundanceProfile:
    """Merge a second kaiju2table (rank genus) as the profile's genus rows."""
    genus_profile = parse_kaiju_table(genus_table)
    profile.genus = genus_profile.species
    return profile


# ---------------------------------------------------------------------------
# MetaPhlAn
# ---------------------------------------------------------------------------

_METAPHLAN_RANKS = {"s": "species", "g": "genus"}


def _metaphlan_latin(clade: str) -> str:
    """``s__Escherichia_coli`` → ``Escherichia coli``."""
    body = clade.split("__", 1)[1] if "__" in clade else clade
    return body.replace("_", " ").strip()


def parse_metaphlan_profile(path: str | Path) -> AbundanceProfile:
    """MetaPhlAn profile (v3/v4 layout) → species + genus rows.

    Plain ``rel_ab`` profiles carry ``relative_abundance`` (percentage, no
    reads). ``rel_ab_w_read_stats`` adds ``estimated_number_of_reads_from_the_
    clade``; the header is parsed by name so the reads land in ``TaxonAbundance``
    when present.
    """
    lines = [ln for ln in Path(path).read_text().splitlines() if ln.strip()]

    i_taxid, i_abundance, i_reads = 1, 2, None
    for line in lines:
        if not line.startswith("#"):
            continue
        header = [c.strip().lstrip("#").strip().lower() for c in line.split("\t")]
        for idx, name in enumerate(header):
            if name in ("ncbi_tax_id", "clade_taxid"):
                i_taxid = idx
            elif name == "relative_abundance":
                i_abundance = idx
            elif name.startswith("estimated_number_of_reads"):
                i_reads = idx
        break

    species: list[TaxonAbundance] = []
    genus: list[TaxonAbundance] = []
    for cols in (_ln.split("\t") for _ln in lines):
        if len(cols) <= max(i_taxid, i_abundance):
            continue
        first = cols[0]
        if first.startswith("#") or not first:
            continue
        parts = first.split("|")
        clade = parts[-1]
        if len(clade) < 4 or "__" not in clade:
            continue
        rank_prefix = clade[: clade.index("__")]
        rank = _METAPHLAN_RANKS.get(rank_prefix)
        if rank is None:  # k__/p__/c__/o__/f__/t__ and friends are skipped
            continue
        reads = None
        if i_reads is not None and i_reads < len(cols):
            reads = _to_int(cols[i_reads])
        taxon = TaxonAbundance(
            name=_metaphlan_latin(clade),
            taxid=_to_int(cols[i_taxid]),
            fraction=(_to_float(cols[i_abundance]) or 0.0) / 100.0,
            reads=reads,
        )
        (species if rank == "species" else genus).append(taxon)
    species.sort(key=lambda t: t.fraction, reverse=True)
    genus.sort(key=lambda t: t.fraction, reverse=True)
    return AbundanceProfile(method=METAPHLAN, species=species, genus=genus)


# ---------------------------------------------------------------------------
# KMCP
# ---------------------------------------------------------------------------


def parse_kmcp_profile(path: str | Path) -> AbundanceProfile:
    """KMCP ``compute profile`` output → species-level rows.

    KMCP reports per-reference rows; when ``taxid``/``taxname`` columns are
    present (``--taxid-map``) rows are aggregated by taxid. Genus rows are not
    part of the format — the 识别网 adapter synthesises them from species.
    """
    lines = [ln for ln in Path(path).read_text().splitlines() if ln.strip()]
    if not lines:
        return AbundanceProfile(method=KMCP)

    header = [c.lstrip("#").strip() for c in lines[0].split("\t")]

    def col(*names: str) -> int | None:
        for name in names:
            if name in header:
                return header.index(name)
        return None

    i_taxid, i_rank = col("taxid"), col("rank")
    i_taxname, i_refname = col("taxname"), col("refname")
    i_reads, i_ureads = col("reads"), col("ureads")
    i_pct = col("percentage", "percent")
    if i_taxid is None or (i_taxname is None and i_refname is None):
        raise ValueError(
            "KMCP profile lacks taxid/taxname columns — re-run `kmcp compute profile` "
            "with --taxid-map (and a taxdump) so rows can be mapped to taxa"
        )

    agg: dict[int, TaxonAbundance] = {}
    agg_pct: dict[int, float] = {}
    for line in lines[1:]:
        cols = line.split("\t")
        if len(cols) < len(header):
            continue
        taxid = _to_int(cols[i_taxid])
        if taxid is None:
            continue
        if i_rank is not None and cols[i_rank].strip() not in ("species", ""):
            continue
        name = (cols[i_taxname] if i_taxname is not None else cols[i_refname]).strip()
        reads = _to_int(cols[i_reads] if i_reads is not None else None)
        if reads is None and i_ureads is not None:
            reads = _to_int(cols[i_ureads])
        if taxid in agg:
            row = agg[taxid]
            if row.reads is not None and reads is not None:
                row.reads += reads
            agg_pct[taxid] += _to_float(cols[i_pct]) if i_pct is not None else 0.0
            continue
        agg[taxid] = TaxonAbundance(name=name, taxid=taxid, reads=reads)
        agg_pct[taxid] = _to_float(cols[i_pct]) if i_pct is not None else 0.0

    rows = list(agg.values())
    fracs = [agg_pct[t] for t in agg]
    _normalise_fractions(rows, fracs)
    return AbundanceProfile(
        method=KMCP,
        species=rows,
        genus=[],
        total_reads=sum(r.reads or 0 for r in rows),
    )


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


def detect_profiler(path: str | Path) -> str:
    """Sniff a profile file: kraken2 | bracken | centrifuge | kaiju | metaphlan |
    kmcp | sylph.

    Headers are checked first (every tool except centrifuge and kraken2 emits
    one); centrifuge is told by its seven name-led columns, kraken2 by the
    percent-led rank-code layout.
    """
    text = Path(path).read_text()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError(f"empty profile: {path}")
    first = lines[0].split("\t")

    header = " ".join(first).lower()
    # metaphlan: header comments on the first lines, clade rows after
    head = " ".join(" ".join(ln.split("\t")) for ln in lines[:5]).lower()
    if "clade_name" in head or any(
        ln.split("\t")[0].startswith(("k__", "p__", "g__", "s__")) for ln in lines[:5]
    ):
        return METAPHLAN
    if "taxon_name" in header and "taxon_id" in header:
        return KAIJU
    if header.startswith("ref ") or first[0].strip("#").strip() == "ref":
        return KMCP
    if "taxrank" in header or ("numreads" in header and "taxid" in header):
        return CENTRIFUGE
    if "taxonomy_lvl" in header or ("tax_id" in header and first[0].lower() == "name"):
        return "bracken"
    if "genome_file" in header or "adjusted_ani" in header:
        return "sylph"

    # headerless formats: centrifuge leads with a name, kraken2 with a percent
    if len(first) >= 6 and (
        _to_float(first[0]) is None
        and _to_int(first[1]) is not None
        and first[2].strip().lower() in _CF_RANKS
        and _to_int(first[3]) is not None
    ):
        return CENTRIFUGE

    for line in lines[:200]:  # kraken2 kreport has no header
        cols = line.split("\t")
        if len(cols) < 6:
            continue
        code = cols[3].strip()
        if _to_float(cols[0]) is not None and code in _KRANKS and _to_int(cols[4]) is not None:
            return "kraken2"
    raise ValueError(f"unrecognised profile format: {path}")


__all__ = [
    "AbundanceProfile",
    "CENTRIFUGE",
    "KAIJU",
    "KMCP",
    "METAPHLAN",
    "TaxonAbundance",
    "attach_kaiju_genus",
    "detect_profiler",
    "parse_centrifuge_report",
    "parse_kaiju_table",
    "parse_kmcp_profile",
    "parse_metaphlan_profile",
]
