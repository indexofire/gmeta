"""Host sequence removal via bowtie2 (mNGS standard recipe).

Maps reads against a host reference index and keeps the unaligned reads
(``--un-con``) for downstream metagenomic profiling. The mapping stats are
parsed from bowtie2's stderr summary.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from gmeta.config import which
from gmeta.engine._env import require_bin, run_checked

_BOWTIE2_HINT = "bowtie2 not found — pixi add bowtie2"

_STATS_RE = re.compile(
    r"(?P<total>\d+) reads; of these:\s*"
    r".*?(?P<conc>\d+) \([\d.]+%\) were paired; of these:\s*"
    r".*?(?P<conc_aligned>\d+) \([\d.]+%\) aligned concordantly 0 times.*?"
    r"(?P<overall>\d+\.\d+)% overall alignment rate",
    re.DOTALL,
)


@dataclass
class HostRemovalStats:
    host_reads: int = 0
    clean_reads: int = 0
    total_reads: int = 0
    host_rate: float = 0.0

    def to_dict(self) -> dict[str, int | float]:
        return {
            "host_reads": self.host_reads,
            "clean_reads": self.clean_reads,
            "total_reads": self.total_reads,
            "host_rate": round(self.host_rate, 6),
        }


def parse_bowtie2_stats(stderr_text: str, paired: bool) -> HostRemovalStats:
    """Extract read counts from a bowtie2 summary block.

    ``overall alignment rate`` is a percentage of reads (pairs count once when
    paired); counts here are normalised to whole reads to match fastp output.
    """
    total_m = re.search(r"(\d+) reads; of these:", stderr_text)
    rate_m = re.search(r"([\d.]+)% overall alignment rate", stderr_text)
    if not total_m or not rate_m:
        raise ValueError("could not parse bowtie2 summary")
    total = int(total_m.group(1))
    rate = float(rate_m.group(1)) / 100.0
    units = total * (2 if paired else 1)
    host_units = round(units * rate)
    return HostRemovalStats(
        host_reads=host_units,
        clean_reads=units - host_units,
        total_reads=units,
        host_rate=rate,
    )


def run_host_removal(
    reads: Sequence[str | Path],
    host_index: str,
    out_dir: str | Path,
    threads: int = 4,
    *,
    extra_args: Sequence[str] = (),
) -> tuple[list[Path], HostRemovalStats]:
    """Remove host reads; returns ``(clean_fastq_paths, stats)``.

    ``--very-sensitive`` plus ``--un-con`` is the mNGS recipe: anything that
    aligns to the host index is discarded, survivors stay paired.
    """
    bt2_bin = require_bin("bowtie2", hint=_BOWTIE2_HINT, resolver=which)
    work = Path(out_dir)
    work.mkdir(parents=True, exist_ok=True)

    inputs = [str(f) for f in reads]
    paired = len(inputs) == 2
    clean_r1 = work / "nonhost_R1.fq.gz"
    clean_r2 = work / "nonhost_R2.fq.gz"

    cmd = [
        bt2_bin,
        "-x",
        str(host_index),
        "--threads",
        str(threads),
        "--very-sensitive",
        "--no-unal",
    ]
    if paired:
        cmd += ["-1", inputs[0], "-2", inputs[1], "--un-con-gz", str(work / "nonhost_R")]
        outputs = [clean_r1, clean_r2]
    else:
        cmd += ["-U", inputs[0], "--un-gz", str(work / "nonhost_R")]
        outputs = [clean_r1]
    cmd += list(extra_args)
    # bowtie2 writes its summary to stderr; keep stdout quiet.
    proc = run_checked(
        cmd + ["-S", str(work / "host_mapped.sam")],
        timeout=7200,
        name="bowtie2 host removal failed",
        truncate=2000,
    )
    stats = parse_bowtie2_stats(proc.stderr, paired)
    return outputs, stats
