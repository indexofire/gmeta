# Usage

Three command families share the same parsers and report model:

| Command | Input | Output |
| --- | --- | --- |
| [`gmeta run`](cli.md#run) | FASTQ | pipeline: QC → host removal → profiling → reports |
| [`gmeta report`](cli.md#report) | profiler result files | JSON/HTML/Excel/PDF report |
| [`gmeta net build`](network.md) | profiler result files | 识别网 submission workbook |

## Method matrix

All six profilers are both **executable** (`gmeta run -m <method>`) and
**importable** (`gmeta report` / `gmeta net build`):

| Method | Execute | Import formats |
| --- | :---: | --- |
| kraken2 + bracken | ✅ | kreport, bracken table |
| sylph | ✅ | profile TSV |
| centrifuge | ✅ | native report, kreport (via centrifuge-kreport) |
| kaiju | ✅ | kaiju2table (species + genus) |
| metaphlan | ✅ | profile (rel_ab / rel_ab_w_read_stats) |
| kmcp | ✅ | compute profile TSV (17 columns) |

## Where to go

- [CLI reference](cli.md) — every flag of run/report/db
- [识别网 export](network.md) — submission workbook deep-dive
- [Supported profilers](profilers.md) — input formats and semantics per tool
- [Coverage](coverage.md) — how 种基因组覆盖度 is computed
