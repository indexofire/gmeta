"""Command-line interface for gmeta.

Two entry paths share the same profilers and report model:

* ``gmeta run`` — full pipeline from FASTQ: fastp QC → host removal →
  kraken2+bracken (or sylph) → reports in every selected format.
* ``gmeta report`` — parse already-existing result files into the same
  reports, for samples analysed upstream by other pipelines.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from gmeta import __version__
from gmeta.analysis import profile_kraken2, profile_sylph
from gmeta.analysis.host import run_host_removal
from gmeta.analysis.qc import run_fastp
from gmeta.report import build_report, write_report
from gmeta.report.models import SampleInfo

HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}

_FORMATS = ["json", "html", "xlsx", "pdf"]

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure root logging. Call once from the CLI entry point."""
    if verbose and quiet:
        raise ValueError("verbose and quiet cannot be enabled together")
    level = logging.DEBUG if verbose else logging.ERROR if quiet else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _info(msg: str) -> None:
    click.echo(msg, err=True)


def _threads_option(help_text: str):
    def decorate(func):
        return click.option(
            "-t",
            "--threads",
            type=click.IntRange(min=1),
            default=4,
            show_default=True,
            help=help_text,
        )(func)

    return decorate


# Generic artifact names written by gmeta run / profilers; when a file is
# called one of these, the sample id comes from its directory instead
# (gmeta-out/<sample>/pipeline/kreport.txt → <sample>).
_GENERIC_PROFILE_STEMS = frozenset(
    {"kreport", "bracken", "profile", "kaiju", "species", "genus", "centrifuge", "search"}
)


def _sample_id_from_profile(path: str | Path) -> str:
    """Sample id for a profiler output file.

    Priority: the ``sample.json`` written by ``gmeta run`` beside its
    artifacts (exact id even when the output directory is named differently),
    then a specific filename (``FZZJ26HZSC0015.report`` → that id), then the
    ``<outdir>/<sample>/pipeline/`` directory, otherwise the stem.
    """
    p = Path(path)
    recorded = p.parent / "sample.json"
    if recorded.is_file():
        try:
            sample_id = json.loads(recorded.read_text(encoding="utf-8")).get("sample_id")
        except (OSError, ValueError):
            sample_id = None
        if sample_id:
            return str(sample_id)
    stem = p.stem
    for suffix in (".kreport", ".report", ".profile", ".tsv"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if (
        (stem.lower() in _GENERIC_PROFILE_STEMS or not stem)
        and p.parent.name == "pipeline"
        and p.parent.parent.name
    ):
        return p.parent.parent.name
    return stem


@click.group(
    context_settings=HELP_SETTINGS,
    invoke_without_command=True,
    no_args_is_help=True,
)
@click.option("-V", "--version", is_flag=True, help="Show the version and exit.")
@click.option(
    "-J", "--json", "version_json", is_flag=True, help="With --version: emit version JSON."
)
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error logging.")
@click.pass_context
def main(ctx: click.Context, version: bool, version_json: bool, verbose: bool, quiet: bool) -> None:
    """gmeta — metagenomic (mNGS) profiling and surveillance reporting.

    Profiles sequencing reads with kraken2+bracken or sylph and renders
    国家致病菌识别网-style surveillance reports (JSON/HTML/Excel/PDF).
    """
    if version:
        if version_json:
            print(json.dumps({"tool": "gmeta", "version": __version__}))
        else:
            print(f"gmeta, version {__version__}")
        sys.exit(0)
    if verbose and quiet:
        raise click.UsageError("--verbose and --quiet cannot be used together")
    setup_logging(verbose, quiet)
    ctx.ensure_object(dict)


@main.group("db", context_settings=HELP_SETTINGS)
def db_group() -> None:
    """Inspect reference database directories."""


@db_group.command("fetch", context_settings=HELP_SETTINGS)
@click.argument(
    "targets",
    nargs=-1,
    type=click.Choice(
        [
            "all",
            "kraken2",
            "centrifuge",
            "kaiju",
            "metaphlan",
            "kmcp",
            "sylph",
            "taxdump",
            "host",
            "refs",
        ]
    ),
)
@click.option(
    "-O",
    "--out-dir",
    type=click.Path(file_okay=False),
    default="db-fetch",
    show_default=True,
    help="Directory for the generated scripts.",
)
@click.option(
    "--db-root",
    type=click.Path(file_okay=False),
    default=None,
    help="Database root the scripts install into (default: $GMETA_DB_DIR or gmeta data/db).",
)
@click.option(
    "--taxids",
    default=None,
    help="Comma-separated species taxids for the refs target (coverage references).",
)
@click.option(
    "--missing-refs",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="TSV from `gmeta net build --missing-refs-out`; its taxid column feeds refs.",
)
def db_fetch(
    targets: tuple[str, ...],
    out_dir: str,
    db_root: str | None,
    taxids: str | None,
    missing_refs: str | None,
) -> None:
    """Generate database download scripts (NOT executed — review URLs first).

    Databases are tens of GB; each script is resumable and verifies the
    layout gmeta expects. TARGETS: kraken2 centrifuge kaiju metaphlan kmcp
    sylph taxdump host refs (default: all except refs). The refs target
    needs --taxids or --missing-refs.
    """
    from gmeta.config import DB_DIR
    from gmeta.dbfetch import TARGET_HELP, TARGETS, write_fetch_scripts

    refs_taxids: list[str] = []
    if taxids:
        refs_taxids += [t.strip() for t in taxids.split(",") if t.strip()]
    if missing_refs:
        for lineno, line in enumerate(Path(missing_refs).read_text().splitlines()):
            if not line.strip() or (lineno == 0 and line.lower().startswith("sample_id")):
                continue
            cols = line.split("\t")
            if len(cols) >= 2 and cols[1].strip().isdigit():
                refs_taxids.append(cols[1].strip())
    refs_taxids = list(dict.fromkeys(refs_taxids))  # de-dupe, keep order

    if "refs" in targets and not refs_taxids:
        raise click.UsageError("the refs target needs --taxids or --missing-refs")
    if refs_taxids and "refs" not in targets and "all" not in targets:
        raise click.UsageError("--taxids/--missing-refs are only used with the refs target")

    if not targets or "all" in targets:
        wanted = sorted(TARGETS)
        if refs_taxids:
            wanted.append("refs")
    else:
        wanted = list(targets)

    try:
        scripts = write_fetch_scripts(
            wanted,
            out_dir,
            str(Path(db_root) if db_root else DB_DIR),
            refs_taxids=refs_taxids or None,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    _info(f"generated {len(scripts)} script(s) in {out_dir} — review, then run:")
    for script in scripts:
        _info(f"  bash {script}")
    for target in wanted:
        _info(f"  [{target}] {TARGET_HELP[target]}")


@db_group.command("list", context_settings=HELP_SETTINGS)
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
    help="Output format.",
)
def db_list(output_format: str) -> None:
    """Show every supported database: path, readiness, and what is missing."""
    from gmeta.config import DB_DIR
    from gmeta.dbstate import probe_databases, probes_to_dict

    probes = probe_databases(DB_DIR)

    if output_format == "json":
        click.echo(json.dumps(probes_to_dict(DB_DIR, probes), indent=2, ensure_ascii=False))
        return

    from rich.console import Console
    from rich.table import Table

    def _short(value: str) -> str:
        return value.replace(str(DB_DIR) + "/", "")

    table = Table(title=f"gmeta databases ({DB_DIR})", show_lines=False)
    table.add_column("工具", style="bold", no_wrap=True)
    table.add_column("状态")
    table.add_column("路径", overflow="fold")
    table.add_column("说明", overflow="fold")
    for probe in probes:
        state = "[green]✓ ready[/green]" if probe.ready else "[red]✗ missing[/red]"
        table.add_row(probe.tool, state, _short(probe.path), _short(probe.detail))
    Console(stderr=False).print(table)
    click.echo("获取缺失数据库: gmeta db fetch <工具>  (生成下载脚本, 不代执行)", err=True)


def _run_pipeline(
    reads: list[str],
    sample_id: str,
    method: str,
    db_dir: str | None,
    host_index: str | None,
    outdir: Path,
    threads: int,
    formats: list[str],
    sample: SampleInfo,
) -> None:
    """QC → host removal → profiling → one report file per selected format."""
    if len(reads) not in (1, 2):
        raise click.UsageError("provide one FASTQ (single-end) or two (paired)")

    work = outdir / "pipeline"
    work.mkdir(parents=True, exist_ok=True)

    _info(f"[{sample_id}] fastp QC …")
    clean_reads, fastp_json = run_fastp(reads, work, threads)

    host_stats = None
    if host_index:
        _info(f"[{sample_id}] host removal (bowtie2) …")
        clean_reads, host_stats = run_host_removal(clean_reads, host_index, work, threads)

    report_kwargs: dict[str, str | None] = {}
    if method == "kraken2":
        _info(f"[{sample_id}] kraken2 + bracken …")
        profile = profile_kraken2(clean_reads, db_dir, threads, work_dir=work)
        report_kwargs = {
            "bracken_path": str(work / "bracken.txt"),
            "kreport_path": str(work / "kreport.txt"),
        }
    elif method == "sylph":
        _info(f"[{sample_id}] sylph …")
        profile = profile_sylph(clean_reads, db_dir, threads, work_dir=work)
        report_kwargs = {"sylph_profile": str(work / "profile.tsv")}
    elif method == "centrifuge":
        _info(f"[{sample_id}] centrifuge …")
        from gmeta.analysis.centrifuge import profile_centrifuge

        profile = profile_centrifuge(clean_reads, db_dir, threads, work_dir=work)
        report_kwargs = {"kreport_path": str(work / "kreport.txt")}
    elif method == "kaiju":
        _info(f"[{sample_id}] kaiju …")
        from gmeta.analysis.kaiju import profile_kaiju

        profile = profile_kaiju(clean_reads, db_dir, threads, work_dir=work)
        report_kwargs = {
            "kaiju_table": str(work / "kaiju.species.tsv"),
            "kaiju_genus_table": str(work / "kaiju.genus.tsv"),
        }
    elif method == "metaphlan":
        _info(f"[{sample_id}] metaphlan …")
        from gmeta.analysis.metaphlan import profile_metaphlan

        profile = profile_metaphlan(clean_reads, db_dir, threads, work_dir=work)
        report_kwargs = {"metaphlan_profile": str(work / "profile.tsv")}
    elif method == "kmcp":
        _info(f"[{sample_id}] kmcp …")
        from gmeta.analysis.kmcp import profile_kmcp

        profile = profile_kmcp(clean_reads, db_dir, threads, work_dir=work)
        report_kwargs = {"kmcp_profile": str(work / "profile.tsv")}
    else:  # pragma: no cover - guarded by click.Choice
        raise click.UsageError(f"unknown method {method!r}")

    report = build_report(
        sample_id=sample_id,
        fastp_json=str(fastp_json),
        sample=sample,
        database=profile.database.get("path"),
        **report_kwargs,  # type: ignore[arg-type]
    )
    if method == "centrifuge":  # build_report labels kreport input as kraken2_bracken
        report.method = method
    if host_stats is not None:
        report.qc.host_reads = host_stats.host_reads
        report.qc.host_rate = host_stats.host_rate

    # record the sample id beside the artifacts: the output directory name may
    # not match the reads prefix (gmeta run -s X -O arbitrary_dir)
    (work / "sample.json").write_text(
        json.dumps({"sample_id": sample_id}), encoding="utf-8"
    )
    # artifacts (kreport/bracken/profile/tables) live under work/ — record them
    for name in (
        "kreport.txt",
        "bracken.txt",
        "profile.tsv",
        "centrifuge.tsv",
        "kaiju.species.tsv",
        "kaiju.genus.tsv",
    ):
        artifact = work / name
        if artifact.is_file():
            _info(f"[{sample_id}] artifact: {artifact}")

    for fmt in formats:
        target = outdir / f"{sample_id}.report.{fmt}"
        write_report(report, target)
        _info(f"[{sample_id}] wrote {target}")
    return report


def _run_batch(
    samples: list[dict[str, object]],
    method: str,
    db_dir: str | None,
    host_index: str | None,
    outdir: Path,
    threads: int,
    jobs: int,
    formats: list[str],
    sample_defaults: dict[str, str | None],
) -> None:
    """Profile a manifest of samples; per-sample outdirs + JSONL on stdout.

    Manifest order is preserved in the output even with ``--jobs > 1``.
    """
    from concurrent.futures import ThreadPoolExecutor

    def one(sample: dict[str, object]) -> str:
        sample_id_ = str(sample["id"])
        files = list(sample["files"])  # type: ignore[arg-type]
        info = SampleInfo(sample_id=sample_id_, **sample_defaults)  # type: ignore[arg-type]
        try:
            report = _run_pipeline(
                files,
                sample_id_,
                method,
                db_dir,
                host_index,
                outdir / sample_id_,
                threads,
                formats,
                info,
            )
        except (RuntimeError, click.UsageError) as exc:
            return json.dumps({"sample": sample_id_, "error": str(exc)})
        return json.dumps({"sample": sample_id_, "report": json.loads(report.model_dump_json())})

    if jobs > 1:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            for line in pool.map(one, samples):
                click.echo(line)
    else:
        for sample in samples:
            click.echo(one(sample))


@main.command("run", context_settings=HELP_SETTINGS)
@click.argument("reads", nargs=-1, required=False, type=click.Path(exists=True))
@click.option(
    "-s",
    "--sample-id",
    default=None,
    help="Sample identifier (single-sample runs; batches derive ids from filenames).",
)
@click.option(
    "-S",
    "--samples",
    "samples_manifest",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Batch manifest: sample_id<TAB>reads [<TAB>reads2] per line.",
)
@click.option(
    "-J",
    "--jobs",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="Concurrent samples in batch runs.",
)
@click.option(
    "-m",
    "--method",
    type=click.Choice(["kraken2", "sylph", "centrifuge", "kaiju", "metaphlan", "kmcp"]),
    default="kraken2",
    show_default=True,
    help="Profiling method (executed by gmeta).",
)
@click.option("-D", "--db-dir", type=click.Path(file_okay=False), help="Profiler database root.")
@click.option(
    "--host-index",
    type=click.Path(),
    default=None,
    help="bowtie2 host index prefix; skip host removal when omitted.",
)
@click.option(
    "-O",
    "--outdir",
    type=click.Path(file_okay=False),
    default=None,
    help="Output directory (single: gmeta-out/<sample-id>; batch: gmeta-out/<sample>/*).",
)
@click.option(
    "-f",
    "--format",
    "formats",
    type=click.Choice(_FORMATS),
    multiple=True,
    default=["json", "html"],
    show_default=True,
    help="Report formats to write (repeatable).",
)
@click.option("--sample-type", default=None, help="样本类型（血清/脑脊液/…）.")
@click.option("--platform", default=None, help="Sequencing platform.")
@click.option("--lab", default=None, help="检测单位.")
@click.option("--operator", default=None, help="检测人员.")
@click.option("--sequencing-date", default=None, help="Sequencing date (YYYY-MM-DD).")
@_threads_option("Threads for fastp/bowtie2/profiler.")
def run_cmd(
    reads: tuple[str, ...],
    sample_id: str | None,
    samples_manifest: str | None,
    jobs: int,
    method: str,
    db_dir: str | None,
    host_index: str | None,
    outdir: str | None,
    formats: tuple[str, ...],
    sample_type: str | None,
    platform: str | None,
    lab: str | None,
    operator: str | None,
    sequencing_date: str | None,
    threads: int,
) -> None:
    """Full pipeline: FASTQ → QC → host removal → profiling → reports.

    One sample: pass 1–2 FASTQ plus -s (or let the id derive from the
    filename). Batches: a --samples manifest, or ≥3 positional reads grouped
    by mate markers (A_R1 A_R2 B_R1 B_R2 → two samples) — one JSONL line per
    sample on stdout.
    """
    from gmeta.samples import manifest_from_positional, read_samples_manifest

    if samples_manifest and reads:
        raise click.UsageError("pass either READS or --samples, not both")
    if not samples_manifest and not reads:
        raise click.UsageError("missing input: pass reads or --samples")

    sample_defaults = {
        "sample_type": sample_type,
        "platform": platform,
        "lab": lab,
        "operator": operator,
        "sequencing_date": sequencing_date,
    }

    # ---- batch dispatch --------------------------------------------------
    manifest: list[dict[str, object]] | None = None
    if samples_manifest:
        try:
            manifest = read_samples_manifest(samples_manifest)
        except ValueError as exc:
            raise click.UsageError(str(exc)) from exc
    elif len(reads) > 2 or (len(reads) == 2 and sample_id is None):
        manifest = manifest_from_positional(list(reads))

    if manifest is not None:
        if sample_id and len(manifest) == 1:
            manifest[0]["id"] = sample_id
        out = Path(outdir) if outdir else Path("gmeta-out")
        _info(f"batch: {len(manifest)} sample(s), jobs={jobs}")
        _run_batch(
            manifest,
            method,
            db_dir,
            host_index,
            out,
            threads,
            jobs,
            list(formats),
            sample_defaults,  # type: ignore[arg-type]
        )
        return

    # ---- single sample ---------------------------------------------------
    if not reads:
        raise click.UsageError("missing input: pass reads or --samples")
    if len(reads) not in (1, 2):
        raise click.UsageError("provide one FASTQ (single-end) or two (paired)")
    from gmeta.samples import sample_id as derive_sample_id

    resolved_id = sample_id or derive_sample_id(list(reads))
    out = Path(outdir) if outdir else Path("gmeta-out") / resolved_id
    sample = SampleInfo(sample_id=resolved_id, **sample_defaults)  # type: ignore[arg-type]
    report = _run_pipeline(
        list(reads),
        resolved_id,
        method,
        db_dir,
        host_index,
        out,
        threads,
        list(formats),
        sample,
    )
    click.echo(report.model_dump_json(indent=2))


@main.group("net", context_settings=HELP_SETTINGS)
def net_group() -> None:
    """国家致病菌识别网 submission format (混合样本 template)."""


@net_group.command("build", context_settings=HELP_SETTINGS)
@click.argument("profiles", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--kingdom",
    default="bacteria",
    show_default=True,
    metavar="KINGDOM[+KINGDOM...]",
    help=(
        "Taxonomic kingdom(s) to report, '+'-joined (e.g. viruses+bacteria). "
        "Default bacteria — CPIN reports bacteria only; all = no filter."
    ),
)
@click.option(
    "--sample-id",
    "sample_id_override",
    default=None,
    help="Override the derived sample id (single input only; fix reads matching).",
)
@click.option(
    "--profiler",
    type=click.Choice(
        ["auto", "kraken2", "bracken", "centrifuge", "kaiju", "metaphlan", "kmcp", "sylph"]
    ),
    default="auto",
    show_default=True,
    help="Profiler of the input files (auto: sniff each file).",
)
@click.option(
    "--kaiju-genus",
    type=click.Path(exists=True),
    default=None,
    help="kaiju2table genus-rank table (adds real genus counts for kaiju inputs).",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default="识别网上报.xlsx",
    show_default=True,
    help="Output workbook (混合样本 + 审核明细 sheets).",
)
@click.option(
    "--top",
    type=click.IntRange(min=1),
    default=10,
    show_default=True,
    help="Species rows per sample.",
)
@click.option(
    "--reads-dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Raw FASTQ directory (enables 种基因组覆盖度).",
)
@click.option(
    "--reads-pattern",
    default="{sample}_R{pair}.fastq.gz",
    show_default=True,
    help="Read filename pattern ({sample}, {pair}).",
)
@click.option(
    "--manifest",
    type=click.Path(exists=True),
    default=None,
    help="Reference genome manifest CSV (accession,species_taxid,…,file_path).",
)
@click.option(
    "--ref-dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Directory of reference genomes ({accession}*.fna / {taxid}*.fna).",
)
@click.option(
    "--split-dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Also write one single-sheet workbook per sample here.",
)
@click.option(
    "--details",
    "details_tsv",
    type=click.Path(),
    default=None,
    help="Extra coverage-details TSV (like the old coverage_details.tsv).",
)
@click.option(
    "--missing-refs-out",
    type=click.Path(),
    default=None,
    help="Write a TSV of species lacking reference genomes (sample, taxid, latin name, reads).",
)
@click.option(
    "--per-species", is_flag=True, help="Align each reference separately (exact, slower)."
)
@click.option(
    "--min-depths",
    default="1,5,10",
    show_default=True,
    help="Coverage thresholds (comma-separated).",
)
@click.option(
    "--preset",
    type=click.Choice(["sr", "map-ont", "map-pb"]),
    default="sr",
    show_default=True,
    help="minimap2 read preset.",
)
@click.option(
    "--auto-refs",
    is_flag=True,
    default=False,
    help=(
        "Download missing reference genomes (NCBI Datasets CLI) before coverage — "
        "one command instead of net build → fetch refs → net build."
    ),
)
@click.option(
    "-J",
    "--jobs",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="Concurrent samples (coverage is the bottleneck; threads stay per-tool).",
)
@_threads_option("Threads for minimap2/samtools.")
def net_build(
    profiles: tuple[str, ...],
    kingdom: str,
    sample_id_override: str | None,
    profiler: str,
    kaiju_genus: str | None,
    output: str,
    top: int,
    reads_dir: str | None,
    reads_pattern: str,
    manifest: str | None,
    ref_dir: str | None,
    split_dir: str | None,
    details_tsv: str | None,
    missing_refs_out: str | None,
    auto_refs: bool,
    per_species: bool,
    min_depths: str,
    preset: str,
    jobs: int,
    threads: int,
) -> None:
    """Build the 混合样本 submission workbook from profiler outputs.

    Supported inputs: kraken2 kreport, bracken, centrifuge report,
    kaiju2table, MetaPhlAn profile, KMCP profile, sylph profile — formats
    are sniffed automatically (or forced with --profiler).
    """
    from gmeta.analysis.coverage import (
        coverage_for_species,
        coverage_per_species,
        discover_reads,
        load_manifest,
    )
    from gmeta.report.network import (
        NetworkRow,
        profile_to_network_rows,
        split_by_sample,
        write_network_xlsx,
    )

    try:
        thresholds = tuple(int(d) for d in min_depths.split(",") if d.strip())
    except ValueError:
        raise click.UsageError("--min-depths must be comma-separated integers") from None
    if not thresholds:
        raise click.UsageError("--min-depths must contain at least one integer")

    manifest_table = load_manifest(manifest) if manifest else None
    want_coverage = reads_dir is not None
    if sample_id_override and len(profiles) > 1:
        raise click.UsageError("--sample-id only applies to a single input file")
    if auto_refs and not want_coverage:
        raise click.UsageError("--auto-refs requires --reads-dir (it fetches coverage references)")
    from gmeta.report.network import parse_kingdoms

    try:
        parse_kingdoms(kingdom)  # validate early → UsageError, not a runtime surprise
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    if auto_refs:
        # pre-pass over every sample: fetch missing references once, before
        # the (possibly parallel) coverage work — avoids download races.
        import os

        from gmeta.config import DB_DIR
        from gmeta.refgenomes import ensure_references

        missing_taxids: set[int] = set()
        for path in profiles:
            probe_id = sample_id_override or _sample_id_from_profile(path)
            try:
                probe_rows, _, _ = profile_to_network_rows(
                    path,
                    probe_id,
                    top=top,
                    manifest=manifest_table,
                    ref_dir=ref_dir,
                    profiler=profiler,
                    kaiju_genus=kaiju_genus,
                    kingdom=kingdom,
                )
            except ValueError as exc:
                raise click.ClickException(str(exc)) from exc
            missing_taxids.update(
                row.taxid for row in probe_rows if row.reference is None and row.taxid
            )
        auto_dir = Path(ref_dir) if ref_dir else DB_DIR / "refs"
        if missing_taxids:
            _info(
                f"auto-refs: {len(missing_taxids)} species missing references — "
                f"fetching into {auto_dir}"
            )
            ready, errors = ensure_references(
                missing_taxids,
                auto_dir,
                api_key=os.environ.get("NCBI_API_KEY") or None,
                on_message=lambda msg: _info(f"[auto-refs] {msg}"),
            )
            _info(f"auto-refs: {len(ready)}/{len(missing_taxids)} reference(s) ready")
            if len(errors) < len(missing_taxids):
                # newly fetched files are <taxid>_<accession>.fna in auto_dir
                ref_dir = str(auto_dir)
        else:
            _info("auto-refs: all references already present")

    def process_one(path: str) -> list[NetworkRow]:
        """Profile one input and fill its coverage columns (thread-safe)."""
        sample_id = sample_id_override or _sample_id_from_profile(path)
        try:
            rows, missing, detected = profile_to_network_rows(
                path,
                sample_id,
                top=top,
                manifest=manifest_table,
                ref_dir=ref_dir,
                profiler=profiler,
                kaiju_genus=kaiju_genus,
                kingdom=kingdom,
            )
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        _info(f"[{sample_id}] {detected}: {len(rows)} species rows")
        if missing:
            _info(
                f"[{sample_id}] no reference genome for {len(missing)} taxid(s): "
                f"{','.join(str(t) for t in missing[:5])}" + ("…" if len(missing) > 5 else "")
            )

        if not want_coverage:
            for row in rows:
                row.coverage_status = "未请求（无 --reads-dir）"
            return rows
        reads = discover_reads(reads_dir, sample_id, reads_pattern)
        if reads is None:
            from gmeta.analysis.coverage import discover_reads_auto

            reads = discover_reads_auto(reads_dir, sample_id)
            if reads is not None:
                _info(
                    f"[{sample_id}] pattern {reads_pattern!r} found nothing; "
                    f"auto-detected reads: {', '.join(Path(r).name for r in reads)}"
                )
        if reads is None:
            from gmeta.analysis.coverage import read_groups

            groups = read_groups(reads_dir)
            if len(groups) == 1:  # single-sample reads dir: use the only group
                only_base, only_files = next(iter(groups.items()))
                reads = only_files
                _info(
                    f"[{sample_id}] no FASTQ matches {sample_id!r}; "
                    f"using the only reads group found: {only_base}"
                )
        if reads is None:
            sample_pattern = reads_pattern.format(sample=sample_id, pair="1")
            from gmeta.analysis.coverage import read_groups

            groups = read_groups(reads_dir)
            candidates = ", ".join(sorted(groups)[:5]) + ("…" if len(groups) > 5 else "")
            hint = f"; FASTQ groups in the dir: {candidates}" if candidates else ""
            _info(
                f"[{sample_id}] no reads found — coverage left blank "
                f"(looked for {Path(reads_dir) / sample_pattern}{hint}; "
                "adjust --reads-pattern, --sample-id, or check the sample id)"
            )
            for row in rows:
                row.coverage_status = "缺reads"
            return rows
        for row in rows:
            if row.reference is None:
                row.coverage_status = "缺参考基因组"
        entries = [
            (row.accession or str(row.taxid), Path(row.reference)) for row in rows if row.reference
        ]
        if not entries:
            _info(
                f"[{sample_id}] no resolvable references — coverage left blank "
                "(provide --manifest or --ref-dir with per-species FASTAs)"
            )
            return rows
        _info(f"[{sample_id}] coverage: {len(entries)} reference(s), {len(reads)} read file(s)")
        runner = coverage_per_species if per_species else coverage_for_species
        try:
            stats = runner(reads, entries, threads=threads, min_depths=thresholds, preset=preset)
        except RuntimeError as exc:
            _info(f"[{sample_id}] coverage failed: {exc}")
            for row in rows:
                if row.reference is not None:
                    row.coverage_status = "覆盖度计算失败"
            return rows
        for row in rows:
            key = row.accession or str(row.taxid)
            stat = stats.get(key)
            if stat is None:
                if row.reference is not None:
                    row.coverage_status = "覆盖度计算失败"
                continue
            row.reference_length = stat.reference_length
            row.mean_depth = stat.mean_depth
            row.coverage_pct_1x = stat.pct_covered.get(1)
            row.coverage_status = "已计算"
        return rows

    if jobs > 1 and len(profiles) > 1:
        from concurrent.futures import ThreadPoolExecutor

        _info(f"batch: {len(profiles)} sample(s), jobs={jobs}, threads={threads}")
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            per_sample = list(pool.map(process_one, profiles))
    else:
        per_sample = [process_one(path) for path in profiles]
    all_rows: list[NetworkRow] = [row for rows in per_sample for row in rows]

    if want_coverage:
        with_cov = sum(1 for row in all_rows if row.coverage_pct_1x is not None)
        _info(
            f"coverage: {with_cov}/{len(all_rows)} row(s) filled "
            f"({len({r.sample_id for r in all_rows if r.coverage_pct_1x is not None})}"
            f"/{len(profiles)} sample(s))"
        )
    no_ref = [row for row in all_rows if row.reference is None]
    if no_ref:
        _info(
            f"missing references: {len(no_ref)} row(s) — supply --manifest/--ref-dir "
            "covering these species"
            + ("" if auto_refs else " (or use --auto-refs to download them)")
            + (" (see --missing-refs-out for the list)" if missing_refs_out else "")
        )

    target = write_network_xlsx(all_rows, output)
    _info(f"wrote {target} ({len(all_rows)} rows, {len(profiles)} sample(s))")
    if split_dir:
        for path in split_by_sample(all_rows, split_dir):
            _info(f"wrote {path}")
    if details_tsv:
        from gmeta.report.network import write_coverage_details

        write_coverage_details(all_rows, details_tsv)
        _info(f"wrote {details_tsv}")
    if missing_refs_out:
        from gmeta.report.network import write_missing_references

        write_missing_references(all_rows, missing_refs_out)
        _info(f"wrote {missing_refs_out} ({len(no_ref)} row(s) without references)")


@main.command("report", context_settings=HELP_SETTINGS)
@click.option("-s", "--sample-id", required=True, help="Sample identifier used in the report.")
@click.option("--kreport", type=click.Path(exists=True), help="kraken2 kreport file.")
@click.option("--bracken", type=click.Path(exists=True), help="bracken species report.")
@click.option("--fastp-json", type=click.Path(exists=True), help="fastp JSON report.")
@click.option("--sylph-profile", type=click.Path(exists=True), help="sylph profile TSV.")
@click.option("--centrifuge", type=click.Path(exists=True), help="centrifuge report file.")
@click.option("--kaiju", type=click.Path(exists=True), help="kaiju2table species-rank table.")
@click.option("--kaiju-genus", type=click.Path(exists=True), help="kaiju2table genus-rank table.")
@click.option("--metaphlan", type=click.Path(exists=True), help="MetaPhlAn profile.")
@click.option("--kmcp", type=click.Path(exists=True), help="KMCP profile TSV.")
@click.option("-D", "--database", default=None, help="Database name/path recorded in the report.")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help="Output file (format from extension: .json/.html/.xlsx/.pdf); default: JSON to stdout.",
)
@click.option("--top", type=click.IntRange(min=1), default=50, show_default=True)
@click.option("--min-fraction", type=float, default=0.0, show_default=True)
@click.option("--sample-type", default=None, help="样本类型.")
@click.option("--platform", default=None, help="Sequencing platform.")
@click.option("--lab", default=None, help="检测单位.")
@click.option("--operator", default=None, help="检测人员.")
@click.option("--sequencing-date", default=None, help="Sequencing date (YYYY-MM-DD).")
def report_cmd(
    sample_id: str,
    kreport: str | None,
    bracken: str | None,
    fastp_json: str | None,
    sylph_profile: str | None,
    centrifuge: str | None,
    kaiju: str | None,
    kaiju_genus: str | None,
    metaphlan: str | None,
    kmcp: str | None,
    database: str | None,
    output: str | None,
    top: int,
    min_fraction: float,
    sample_type: str | None,
    platform: str | None,
    lab: str | None,
    operator: str | None,
    sequencing_date: str | None,
) -> None:
    """Build a report from existing profiler outputs (no re-run)."""
    sources = (bracken, kreport, sylph_profile, centrifuge, kaiju, metaphlan, kmcp)
    if not any(sources):
        raise click.UsageError(
            "need at least one of --bracken / --kreport / --sylph-profile / "
            "--centrifuge / --kaiju / --metaphlan / --kmcp"
        )
    sample = SampleInfo(
        sample_id=sample_id,
        sample_type=sample_type,
        platform=platform,
        lab=lab,
        operator=operator,
        sequencing_date=sequencing_date,
    )
    try:
        report = build_report(
            sample_id=sample_id,
            bracken_path=bracken,
            kreport_path=kreport,
            fastp_json=fastp_json,
            sylph_profile=sylph_profile,
            centrifuge_report=centrifuge,
            kaiju_table=kaiju,
            kaiju_genus_table=kaiju_genus,
            metaphlan_profile=metaphlan,
            kmcp_profile=kmcp,
            sample=sample,
            database=database,
            top=top,
            min_fraction=min_fraction,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc)) from exc
    if output is None:
        click.echo(report.model_dump_json(indent=2))
        return
    target = write_report(report, output)
    _info(f"wrote {target}")


if __name__ == "__main__":  # pragma: no cover
    main()
