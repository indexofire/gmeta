"""Database inventory: probe every supported tool's database layout.

Each probe calls the resolver the corresponding executor uses, so "ready"
in ``gmeta db list`` means the profiler would actually accept the path —
including companion files (bracken kmer_distrib, kaiju names.dmp, kmcp
taxdump) that a bare directory listing would miss.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from gmeta.config import DB_DIR


@dataclass
class DbProbe:
    tool: str
    path: str
    ready: bool
    detail: str


def _probe(tool: str, path: Path, resolver: Callable[[Path], object]) -> DbProbe:
    try:
        resolved = resolver(path)
        # resolvers return a Path (or prefix str for centrifuge) on success
        shown = str(resolved) if isinstance(resolved, (str, Path)) else str(path)
        return DbProbe(tool, shown, True, "ready")
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        return DbProbe(tool, str(path), False, str(exc))


def _probe_host(root: Path) -> DbProbe:
    host = root / "host"
    indexes = sorted(host.glob("*.bt2l")) + sorted(host.glob("*.bt2"))
    if indexes:
        prefix = indexes[0].name.split(".", 1)[0]
        return DbProbe("host", str(host / prefix), True, "ready (bowtie2 index)")
    return DbProbe(
        "host", str(host), False, f"no bowtie2 index in {host} (run: gmeta db fetch host)"
    )


def _probe_taxdump(root: Path) -> DbProbe:
    taxdump = root / "taxdump"
    if (taxdump / "nodes.dmp").is_file() and (taxdump / "names.dmp").is_file():
        return DbProbe("taxdump", str(taxdump), True, "ready (NCBI taxdump)")
    return DbProbe(
        "taxdump",
        str(taxdump),
        False,
        f"nodes.dmp/names.dmp missing in {taxdump} (run: gmeta db fetch taxdump)",
    )


def probe_databases(db_root: str | Path | None = None) -> list[DbProbe]:
    """Probe every database gmeta knows about, in fetch-target order."""
    from gmeta.analysis.centrifuge import resolve_centrifuge_db
    from gmeta.analysis.kaiju import resolve_kaiju_db
    from gmeta.analysis.kmcp import resolve_kmcp_db
    from gmeta.analysis.kraken2 import resolve_kraken2_db
    from gmeta.analysis.metaphlan import resolve_metaphlan_db
    from gmeta.analysis.sylph import resolve_sylph_db

    root = Path(db_root) if db_root else DB_DIR
    return [
        _probe("kraken2", root / "kraken2", resolve_kraken2_db),
        _probe("centrifuge", root / "centrifuge", resolve_centrifuge_db),
        _probe("kaiju", root / "kaiju", resolve_kaiju_db),
        _probe("metaphlan", root / "metaphlan", resolve_metaphlan_db),
        _probe("kmcp", root / "kmcp", resolve_kmcp_db),
        _probe("sylph", root / "sylph", resolve_sylph_db),
        _probe_taxdump(root),
        _probe_host(root),
    ]


def probes_to_dict(db_dir: Path, probes: list[DbProbe]) -> dict[str, object]:
    """Stable JSON shape for `gmeta db list -f json`."""
    return {
        "db_dir": str(db_dir),
        "databases": {
            probe.tool: {"path": probe.path, "ready": probe.ready, "detail": probe.detail}
            for probe in probes
        },
    }


__all__ = ["DbProbe", "probe_databases", "probes_to_dict"]
