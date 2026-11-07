"""Third-party profiler parsers: centrifuge, kaiju, metaphlan, kmcp."""

from __future__ import annotations

from pathlib import Path

import pytest

from gmeta.analysis.profilers import (
    CENTRIFUGE,
    KAIJU,
    KMCP,
    METAPHLAN,
    attach_kaiju_genus,
    detect_profiler,
    parse_centrifuge_report,
    parse_kaiju_table,
    parse_kmcp_profile,
    parse_metaphlan_profile,
)

CENTRIFUGE_REPORT = """Escherichia\t562\tgenus\t4641652\t7227494\t100\t12.5
Escherichia coli\t561\tspecies\t4641652\t6428861\t90\t11.1
Shigella flexneri\t630\tspecies\t4550000\t200\t5\t0.004
Vibrio\t641\tgenus\t5000000\t1000\t50\t0.02
"""

KAIJU_TABLE = """file\tpercent\treads\ttaxon_id\ttaxon_name
sample1.fq\t11.1\t6428861\t562\tBacteria; Escherichia; Escherichia coli
sample1.fq\t0.5\t30000\t630\tBacteria; Shigella; Shigella flexneri
sample1.fq\t0.2\t12000\t662\tBacteria; Vibrio; Vibrio cholerae
"""

KAIJU_GENUS_TABLE = """file\tpercent\treads\ttaxon_id\ttaxon_name
sample1.fq\t11.6\t6460000\t561\tBacteria; Escherichia
sample1.fq\t0.2\t12000\t641\tBacteria; Vibrio
"""

METAPHLAN_PROFILE = """#SampleID\tMetaphlan_Analysis
#clade_name\tNCBI_tax_id\trelative_abundance\tadditional_species
k__Bacteria\t2\t100.000\t
p__Proteobacteria\t1224\t60.123\t
g__Escherichia\t561\t55.5\t
s__Escherichia_coli\t562\t50.5\t
g__Vibrio\t641\t5.0\t
s__Vibrio_cholerae\t662\t4.2\t
"""

KMCP_PROFILE = (
    "#ref\tpercentage\tcoverage\tscore\tchunksFrac\tchunksRelDepth\tchunksRelDepthStd\t"
    "reads\tureads\thicureads\trefsize\trefname\ttaxid\trank\ttaxname\ttaxpath\ttaxpathsn\n"
    "GCF_000005845.2\t55.0\t0.95\t0.9\t0.9\t1.0\t0.01\t6400000\t6000000\t6000000\t4641652\t"
    "Escherichia coli\t562\tspecies\tEscherichia coli\t562\t1224|561|562\n"
    "GCF_000006925.2\t0.6\t0.90\t0.9\t0.9\t1.0\t0.01\t70000\t65000\t65000\t4550000\t"
    "Shigella flexneri\t630\tspecies\tShigella flexneri\t630\t1224|630\n"
    "GCF_999999999.1\t0.5\t0.90\t0.9\t0.9\t1.0\t0.01\t60000\t55000\t55000\t4000000\t"
    "Escherichia coli O157\t562\tspecies\tEscherichia coli\t562\t1224|561|562\n"
)

SYLPH_TSV = """Genome_file\tAdjusted_ANI\tEff_cov\tTaxonomic_abundance
GCF_000005845.2.fna\t96.5\t10.2\t55.0
GCF_000006925.2.fna\t95.1\t2.0\t5.0
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content)
    return path


def test_parse_centrifuge_report(tmp_path: Path) -> None:
    profile = parse_centrifuge_report(_write(tmp_path, "cf.txt", CENTRIFUGE_REPORT))
    assert profile.method == CENTRIFUGE
    by_name = {t.name: t for t in profile.species}
    assert set(by_name) == {"Escherichia coli", "Shigella flexneri"}
    ecoli = by_name["Escherichia coli"]
    assert ecoli.reads == 6428861
    # the tool's own abundance column wins over reads-based recomputation
    assert ecoli.fraction == pytest.approx(0.111)
    genus = {t.name: t for t in profile.genus}
    assert set(genus) == {"Escherichia", "Vibrio"}


def test_parse_kaiju_table_lineage(tmp_path: Path) -> None:
    profile = parse_kaiju_table(_write(tmp_path, "kaiju_species.tsv", KAIJU_TABLE))
    assert profile.method == KAIJU
    by_name = {t.name: t for t in profile.species}
    assert set(by_name) == {"Escherichia coli", "Shigella flexneri", "Vibrio cholerae"}
    ecoli = by_name["Escherichia coli"]
    assert ecoli.taxid == 562 and ecoli.reads == 6428861
    # lineage hint surfaced for the 识别网 adapter
    assert profile._genus_hints["escherichia coli"] == "Escherichia"


def test_attach_kaiju_genus(tmp_path: Path) -> None:
    profile = parse_kaiju_table(_write(tmp_path, "s.tsv", KAIJU_TABLE))
    attach_kaiju_genus(profile, _write(tmp_path, "g.tsv", KAIJU_GENUS_TABLE))
    genus = {t.name: t for t in profile.genus}
    assert set(genus) == {"Escherichia", "Vibrio"}
    assert genus["Escherichia"].reads == 6460000


def test_parse_metaphlan_profile(tmp_path: Path) -> None:
    profile = parse_metaphlan_profile(_write(tmp_path, "mpa.txt", METAPHLAN_PROFILE))
    assert profile.method == METAPHLAN
    by_name = {t.name: t for t in profile.species}
    assert by_name["Escherichia coli"].fraction == pytest.approx(0.505)
    assert by_name["Escherichia coli"].taxid == 562
    genus = {t.name: t for t in profile.genus}
    assert set(genus) == {"Escherichia", "Vibrio"}


def test_parse_kmcp_profile_aggregates_by_taxid(tmp_path: Path) -> None:
    profile = parse_kmcp_profile(_write(tmp_path, "kmcp.tsv", KMCP_PROFILE))
    assert profile.method == KMCP
    by_name = {t.name: t for t in profile.species}
    # two E. coli references aggregate into one taxon
    assert len(profile.species) == 2
    ecoli = by_name["Escherichia coli"]
    assert ecoli.taxid == 562
    assert ecoli.reads == 6400000 + 60000
    assert by_name["Shigella flexneri"].reads == 70000


def test_parse_kmcp_requires_taxid_columns(tmp_path: Path) -> None:
    header_only = "\t".join(
        [
            "ref",
            "percentage",
            "coverage",
            "score",
            "chunksFrac",
            "chunksRelDepth",
            "chunksRelDepthStd",
            "reads",
            "ureads",
            "hicureads",
            "refsize",
        ]
    )
    data_row = "GCF_1\t50.0\t0.9\t0.9\t0.9\t1\t0\t10\t9\t9\t1000\n"
    path = _write(tmp_path, "kmcp_bad.tsv", header_only + "\n" + data_row)
    with pytest.raises(ValueError, match="taxid"):
        parse_kmcp_profile(path)


def test_detect_profiler_formats(tmp_path: Path, kreport_file: Path, bracken_file: Path) -> None:
    assert detect_profiler(kreport_file) == "kraken2"
    assert detect_profiler(bracken_file) == "bracken"
    assert detect_profiler(_write(tmp_path, "cf.txt", CENTRIFUGE_REPORT)) == CENTRIFUGE
    assert detect_profiler(_write(tmp_path, "k.tsv", KAIJU_TABLE)) == KAIJU
    assert detect_profiler(_write(tmp_path, "m.txt", METAPHLAN_PROFILE)) == METAPHLAN
    assert detect_profiler(_write(tmp_path, "k.tsv", KMCP_PROFILE)) == KMCP
    assert detect_profiler(_write(tmp_path, "s.tsv", SYLPH_TSV)) == "sylph"


def test_detect_profiler_rejects_garbage(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unrecognised"):
        detect_profiler(_write(tmp_path, "x.txt", "hello world\nfoo bar\n"))
