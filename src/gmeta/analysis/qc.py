"""Read QC via fastp: run + JSON report parsing."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gmeta.config import which
from gmeta.engine._env import require_bin, run_checked

_FASTP_HINT = "fastp not found — pixi add fastp"


@dataclass
class QcMetrics:
    """The fastp numbers a surveillance report needs, normalised per sample."""

    total_reads: int = 0
    clean_reads: int = 0
    total_bases: int = 0
    clean_bases: int = 0
    q20_rate: float = 0.0
    q30_rate: float = 0.0
    duplication_rate: float = 0.0
    read1_mean_length: int = 0
    read2_mean_length: int = 0
    filtering_result: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_reads": self.total_reads,
            "clean_reads": self.clean_reads,
            "total_bases": self.total_bases,
            "clean_bases": self.clean_bases,
            "q20_rate": round(self.q20_rate, 6),
            "q30_rate": round(self.q30_rate, 6),
            "duplication_rate": round(self.duplication_rate, 6),
            "read1_mean_length": self.read1_mean_length,
            "read2_mean_length": self.read2_mean_length,
            "filtering_result": self.filtering_result,
        }


def parse_fastp_json(path: str | Path) -> QcMetrics:
    """Extract normalised QC metrics from a fastp JSON report.

    fastp reports paired reads as *read pairs* in some keys and *reads* in
    others; everything here is converted to whole reads (×2 for pairs) so
    downstream fractions are unambiguous.
    """
    data = json.loads(Path(path).read_text())
    summary = data.get("summary", {})
    before = summary.get("before_filtering", {})
    after = summary.get("after_filtering", {})

    paired = bool(data.get("read1_before_filtering") and data.get("read2_before_filtering"))
    factor = 2 if paired else 1

    total_reads = int(before.get("total_reads", 0)) * factor
    clean_reads = int(after.get("total_reads", 0)) * factor
    total_bases = int(before.get("total_bases", 0))
    clean_bases = int(after.get("total_bases", 0))

    filtering = {
        key: int(value)
        for key, value in data.get("filtering_result", {}).items()
        if isinstance(value, int)
    }
    return QcMetrics(
        total_reads=total_reads,
        clean_reads=clean_reads,
        total_bases=total_bases,
        clean_bases=clean_bases,
        q20_rate=float(after.get("q20_rate", 0.0)),
        q30_rate=float(after.get("q30_rate", 0.0)),
        duplication_rate=float(data.get("duplication", {}).get("rate", 0.0)),
        read1_mean_length=int(after.get("read1_mean_length", 0)),
        read2_mean_length=int(after.get("read2_mean_length", 0)),
        filtering_result=filtering,
    )


def run_fastp(
    reads: Sequence[str | Path],
    out_dir: str | Path,
    threads: int = 4,
    *,
    qualified_quality_phred: int = 20,
    length_required: int = 50,
) -> tuple[list[Path], Path]:
    """Run fastp on one FASTQ (single-end) or two (paired).

    Returns ``(clean_fastq_paths, fastp_json_path)``; outputs land in
    ``out_dir`` as ``clean_R1.fq.gz`` / ``clean_R2.fq.gz`` / ``fastp.json``.
    """
    fastp_bin = require_bin("fastp", hint=_FASTP_HINT, resolver=which)
    work = Path(out_dir)
    work.mkdir(parents=True, exist_ok=True)

    inputs = [str(f) for f in reads]
    json_path = work / "fastp.json"
    html_path = work / "fastp.html"

    cmd = [
        fastp_bin,
        "--thread",
        str(threads),
        "--qualified_quality_phred",
        str(qualified_quality_phred),
        "--length_required",
        str(length_required),
        "--json",
        str(json_path),
        "--html",
        str(html_path),
        "--detect_adapter_for_pe",
    ]
    if len(inputs) == 2:
        out_r1, out_r2 = work / "clean_R1.fq.gz", work / "clean_R2.fq.gz"
        cmd += [
            "--in1",
            inputs[0],
            "--in2",
            inputs[1],
            "--out1",
            str(out_r1),
            "--out2",
            str(out_r2),
        ]
        outputs = [out_r1, out_r2]
    else:
        out_r1 = work / "clean_R1.fq.gz"
        cmd += ["--in1", inputs[0], "--out1", str(out_r1)]
        outputs = [out_r1]
    run_checked(cmd, timeout=3600, name="fastp failed")
    return outputs, json_path
