"""On-demand reference-genome acquisition for coverage (NCBI Datasets CLI).

`gmeta net build --auto-refs` uses this to collapse the old three-step
workflow (build → missing list → fetch) into one command: missing species
references are downloaded into the refs directory, then coverage runs.

Installed files are named ``<taxid>_<accession>.fna`` so the coverage
resolver matches them via ``--ref-dir`` without a manifest; a ``manifest.csv``
is appended alongside for review/audit.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable, Iterable
from pathlib import Path

_MANIFEST_HEADER = "accession,species_taxid,organism_taxid,scientific_name,file_path\n"

# Flag dialects across CLI versions; first hit wins. v16+ has no `taxid`
# subcommand — numeric ids go through `taxon`.
_SUMMARY_FLAGS: tuple[tuple[str, ...], ...] = (
    ("--reference", "--as-json-lines"),
    ("--reference",),
    ("--as-json-lines",),
    (),
)


def parse_summary(text: str) -> tuple[str, str] | None:
    """(accession, organism_name) from JSON-lines or a pretty JSON document."""
    text = text.strip()
    if not text:
        return None
    try:
        doc = json.loads(text)  # whole document
    except json.JSONDecodeError:
        doc = json.loads(text.splitlines()[0])  # JSON lines
    if isinstance(doc, dict) and "reports" in doc:
        reports = doc.get("reports") or []
        row = reports[0] if reports else {}
    elif isinstance(doc, dict):
        row = doc
    else:
        row = {}
    acc = row.get("accession") or (row.get("accessions") or {}).get("assembly") or ""
    name = (row.get("organism") or {}).get("organism_name") or ""
    if not acc:
        return None
    return acc, name.replace(",", " ")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=1800)


def _cli_error(proc: subprocess.CompletedProcess[str]) -> str:
    lines = [ln for ln in (proc.stderr or "").strip().splitlines() if ln.strip()]
    return lines[-1] if lines else f"exit {proc.returncode}"


def find_assembly(
    datasets_bin: str, taxid: int | str, api_key: str | None = None
) -> tuple[str, str]:
    """(accession, organism_name) for a taxid; raises RuntimeError with the CLI error."""
    last_error = ""
    for flags in _SUMMARY_FLAGS:
        cmd = [datasets_bin, "summary", "genome", "taxon", str(taxid), *flags]
        if api_key:
            cmd += ["--api-key", api_key]
        proc = _run(cmd)
        if proc.returncode != 0:
            last_error = _cli_error(proc)
            continue
        parsed = parse_summary(proc.stdout)
        if parsed:
            return parsed
    detail = f" — CLI: {last_error}" if last_error else ""
    raise RuntimeError(f"no NCBI assembly for taxid {taxid}{detail}")


def _download_genome(
    datasets_bin: str, accession: str, dest: Path, taxid: int | str, api_key: str | None
) -> Path:
    with tempfile.TemporaryDirectory(prefix="gmeta-refs-") as tmp:
        zip_path = Path(tmp) / "g.zip"
        cmd = [
            datasets_bin,
            "download",
            "genome",
            "accession",
            accession,
            "--include",
            "genome",
            "--filename",
            str(zip_path),
        ]
        if api_key:
            cmd += ["--api-key", api_key]
        proc = _run(cmd)
        if proc.returncode != 0:
            raise RuntimeError(f"download failed for {accession} — CLI: {_cli_error(proc)}")
        extracted = Path(tmp) / "x"
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extracted)
        fnas = sorted(extracted.rglob("*.fna"))
        if not fnas:
            raise RuntimeError(f"download for {accession} contained no .fna")
        target = dest / f"{taxid}_{accession}.fna"
        target.write_bytes(fnas[0].read_bytes())
        return target


def ensure_references(
    taxids: Iterable[int | str],
    dest: str | Path,
    *,
    api_key: str | None = None,
    on_message: Callable[[str], None] | None = None,
) -> tuple[dict[int, Path], list[str]]:
    """Download missing references into ``dest``; returns (taxid→path, errors).

    Species already present as ``<taxid>_*.fna`` are skipped (cached). A
    failure for one taxid does not stop the others.
    """
    from gmeta.config import which
    from gmeta.engine._env import require_bin

    tell = on_message or (lambda msg: print(msg, file=sys.stderr))
    datasets_bin = require_bin(
        "datasets",
        hint=(
            "NCBI Datasets CLI not found — conda install -c conda-forge "
            "ncbi-datasets-cli (the gmeta pixi env ships it)"
        ),
        resolver=which,
    )

    out_dir = Path(dest)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "manifest.csv"
    if not manifest.is_file():
        manifest.write_text(_MANIFEST_HEADER, encoding="utf-8")

    ready: dict[int, Path] = {}
    errors: list[str] = []
    for taxid in sorted({int(t) for t in taxids}):
        cached = sorted(out_dir.glob(f"{taxid}_*.fna"))
        if cached:
            ready[taxid] = cached[0]
            continue
        try:
            accession, name = find_assembly(datasets_bin, taxid, api_key)
            tell(f"taxid {taxid} -> {accession} ({name or 'unnamed'})")
            target = _download_genome(datasets_bin, accession, out_dir, taxid, api_key)
        except RuntimeError as exc:
            errors.append(str(exc))
            tell(f"WARN: {exc}")
            continue
        with manifest.open("a", encoding="utf-8") as fh:
            fh.write(f'{accession},{taxid},{taxid},"{name}",{target}\n')
        ready[taxid] = target
    return ready, errors


__all__ = ["ensure_references", "find_assembly", "parse_summary"]
