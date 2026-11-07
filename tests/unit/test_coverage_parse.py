"""Coverage helpers: manifest, reference resolution, reads discovery, combined ref."""

from __future__ import annotations

from pathlib import Path

from gmeta.analysis.coverage import (
    CoverageStats,
    _build_combined_reference,
    discover_reads,
    fasta_sequence_lengths,
    load_manifest,
    resolve_reference,
)

MANIFEST = """accession,species_taxid,organism_taxid,scientific_name,file_path,file_size_bytes
GCF_000005845.2,562,562,Escherichia coli str. K-12,refs/GCF_000005845.2_Ecoli.fna,4641652
GCF_000006925.2,630,632,Shigella flexneri 2a str. 301,missing.fna,0
"""

FASTA_A = ">seqA\nACGTACGTAC\n>seqB\nGGGGCCCC\n"
FASTA_B = ">chr1\nTTTTAAAA\n"


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content)
    return path


def test_load_manifest_relative_paths(tmp_path: Path) -> None:
    manifest = _write(tmp_path, "manifest.csv", MANIFEST)
    refs_dir = tmp_path / "refs"
    refs_dir.mkdir()
    _write(refs_dir, "GCF_000005845.2_Ecoli.fna", FASTA_A)

    entries = load_manifest(manifest)
    assert set(entries) == {562, 630}
    ecoli = entries[562]
    assert ecoli.accession == "GCF_000005845.2"
    assert ecoli.file_path == refs_dir / "GCF_000005845.2_Ecoli.fna"  # resolved
    assert ecoli.file_path.is_file()


def test_resolve_reference_order(tmp_path: Path) -> None:
    manifest = load_manifest(_write(tmp_path, "manifest.csv", MANIFEST))
    refs_dir = tmp_path / "refs"
    refs_dir.mkdir()
    flat = _write(refs_dir, "GCF_000005845.2_Ecoli.fna", FASTA_A)

    # manifest path exists → used directly
    entry, path = resolve_reference(562, manifest, None)
    assert path == flat
    assert entry is not None and entry.accession == "GCF_000005845.2"

    # manifest entry but file missing, ref-dir glob by accession rescues it
    (tmp_path / "missing.fna").unlink(missing_ok=True)
    rescue = tmp_path / "rescue"
    rescue.mkdir()
    rescued = _write(rescue, "GCF_000006925.2_Sflexneri.fna", FASTA_B)
    entry, path = resolve_reference(630, manifest, rescue)
    assert path == rescued

    # no manifest at all → taxid glob
    entry, path = resolve_reference(630, None, rescue)
    assert path is None  # rescue dir has no 630-prefixed file
    taxid_dir = tmp_path / "by_taxid"
    taxid_dir.mkdir()
    by_taxid = _write(taxid_dir, "630_shigella.fna", FASTA_B)
    entry, path = resolve_reference(630, None, taxid_dir)
    assert path == by_taxid

    # nothing resolvable
    entry, path = resolve_reference(999999, manifest, None)
    assert path is None


def test_fasta_sequence_lengths(tmp_path: Path) -> None:
    fasta = _write(tmp_path, "ref.fna", FASTA_A)
    assert fasta_sequence_lengths(fasta) == {"seqA": 10, "seqB": 8}


def test_build_combined_reference(tmp_path: Path) -> None:
    a = _write(tmp_path, "a.fna", FASTA_A)
    b = _write(tmp_path, "b.fna", FASTA_B)
    combined = tmp_path / "combined.fna"
    seq_groups, lengths = _build_combined_reference([("562", a), ("GCF_x", b)], combined)

    assert seq_groups == {"562": ["562__0", "562__1"], "GCF_x": ["GCF_x__0"]}
    assert lengths == {"562__0": 10, "562__1": 8, "GCF_x__0": 8}
    content = combined.read_text()
    assert ">562__0" in content and ">GCF_x__0" in content


def test_discover_reads_paired_and_gz(tmp_path: Path) -> None:
    reads = tmp_path / "reads"
    reads.mkdir()
    _write(reads, "S1_R1.fastq.gz", "")
    _write(reads, "S1_R2.fastq.gz", "")

    found = discover_reads(reads, "S1", "{sample}_R{pair}.fastq.gz")
    assert found is not None and len(found) == 2
    assert found[0].endswith("S1_R1.fastq.gz")

    # one mate missing → None
    assert discover_reads(reads, "S2", "{sample}_R{pair}.fastq.gz") is None


def test_discover_reads_single_end_variant(tmp_path: Path) -> None:
    reads = tmp_path / "reads"
    reads.mkdir()
    _write(reads, "S1.fastq", "")  # pattern says .fq, gz/compressed variants tried
    found = discover_reads(reads, "S1", "{sample}.fq")
    assert found is None  # .fq → .fq.gz tried, but plain .fq.gz absent → None
    _write(reads, "S1.fq.gz", "")
    found = discover_reads(reads, "S1", "{sample}.fq")
    assert found is not None and found[0].endswith("S1.fq.gz")


def test_coverage_stats_to_dict() -> None:
    stats = CoverageStats(reference_length=100, mean_depth=5.0, pct_covered={1: 90.0, 5: 40.0})
    payload = stats.to_dict()
    assert payload["pct_covered_1x"] == 90.0
    assert payload["reference_length"] == 100
