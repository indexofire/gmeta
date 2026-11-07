"""Metagenomic profilers: kraken2/bracken, sylph (ported from gside) plus
centrifuge, kaiju, metaphlan, kmcp executors, third-party profile parsers,
and the mNGS pre-processing steps (fastp QC, bowtie2 host removal).
"""

from gmeta.analysis._envelope import METAGENOMIC, MethodEnvelope
from gmeta.analysis.centrifuge import (
    CentrifugeResult,
    profile_centrifuge,
    resolve_centrifuge_db,
    run_centrifuge,
    run_centrifuge_kreport,
)
from gmeta.analysis.coverage import (
    CoverageStats,
    ManifestEntry,
    coverage_for_species,
    coverage_per_species,
    discover_reads,
    fasta_sequence_lengths,
    load_manifest,
    resolve_reference,
)
from gmeta.analysis.host import HostRemovalStats, run_host_removal
from gmeta.analysis.kaiju import (
    KaijuResult,
    profile_kaiju,
    resolve_kaiju_db,
    run_kaiju,
    run_kaiju2table,
)
from gmeta.analysis.kmcp import (
    KmcpResult,
    profile_kmcp,
    resolve_kmcp_db,
    run_kmcp_profile,
    run_kmcp_search,
)
from gmeta.analysis.kraken2 import (
    Kraken2Result,
    KreportRow,
    KreportSummary,
    parse_bracken,
    parse_kreport,
    profile_kraken2,
    resolve_kraken2_db,
    run_bracken,
    run_kraken2,
)
from gmeta.analysis.metaphlan import (
    MetaphlanResult,
    profile_metaphlan,
    resolve_metaphlan_db,
    run_metaphlan,
)
from gmeta.analysis.profilers import (
    AbundanceProfile,
    TaxonAbundance,
    attach_kaiju_genus,
    detect_profiler,
    parse_centrifuge_report,
    parse_kaiju_table,
    parse_kmcp_profile,
    parse_metaphlan_profile,
)
from gmeta.analysis.qc import QcMetrics, parse_fastp_json, run_fastp
from gmeta.analysis.sylph import SylphResult, ani_confidence, parse_profile, profile_sylph

__all__ = [
    "AbundanceProfile",
    "CentrifugeResult",
    "CoverageStats",
    "HostRemovalStats",
    "KaijuResult",
    "KmcpResult",
    "KreportRow",
    "KreportSummary",
    "Kraken2Result",
    "ManifestEntry",
    "METAGENOMIC",
    "MetaphlanResult",
    "MethodEnvelope",
    "QcMetrics",
    "SylphResult",
    "TaxonAbundance",
    "ani_confidence",
    "attach_kaiju_genus",
    "coverage_for_species",
    "coverage_per_species",
    "detect_profiler",
    "discover_reads",
    "fasta_sequence_lengths",
    "load_manifest",
    "parse_bracken",
    "parse_centrifuge_report",
    "parse_fastp_json",
    "parse_kaiju_table",
    "parse_kmcp_profile",
    "parse_kreport",
    "parse_metaphlan_profile",
    "parse_profile",
    "profile_centrifuge",
    "profile_kaiju",
    "profile_kmcp",
    "profile_kraken2",
    "profile_metaphlan",
    "profile_sylph",
    "resolve_centrifuge_db",
    "resolve_kaiju_db",
    "resolve_kmcp_db",
    "resolve_kraken2_db",
    "resolve_metaphlan_db",
    "resolve_reference",
    "run_bracken",
    "run_centrifuge",
    "run_centrifuge_kreport",
    "run_fastp",
    "run_host_removal",
    "run_kaiju",
    "run_kaiju2table",
    "run_kraken2",
    "run_kmcp_profile",
    "run_kmcp_search",
    "run_metaphlan",
]
