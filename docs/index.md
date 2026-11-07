# gmeta documentation

`gmeta` is a Python CLI for metagenomic (mNGS) profiling and surveillance
reporting. It runs the fastp → host-removal → kraken2/bracken (or sylph)
pipeline from FASTQ, imports results from seven third-party profilers, and
renders 国家致病菌识别网 (China CDC pathogen surveillance network) submission
workbooks plus JSON/HTML/Excel/PDF reports.

## Start here

| I want to… | Read |
| --- | --- |
| Install gmeta and run a first sample | [Quick start](installation/quick-start.md) |
| Learn every CLI flag | [CLI reference](usage/cli.md) |
| Produce the 识别网 submission workbook | [识别网 export](usage/network.md) |
| Import centrifuge/kaiju/metaphlan/kmcp results | [Supported profilers](usage/profilers.md) |
| Understand 种基因组覆盖度 computation | [Coverage](usage/coverage.md) |
| Prepare kraken2/sylph/reference databases | [Databases](installation/databases.md) |
| Read the exact file formats | [File formats](reference/formats.md) |
| Consume JSON output safely | [JSON contract](reference/json-contract.md) |

## What gmeta does

```text
FASTQ reads ──────── fastp QC → bowtie2 host removal ─┐
existing results ─── kraken2 / bracken / centrifuge ──┼──→ abundance profile
                     kaiju / metaphlan / kmcp / sylph ─┘         │
                                                                    ├─→ JSON / HTML / Excel / PDF report
raw reads + refs ─── minimap2 + samtools ──→ 种基因组覆盖度 ──┴─→ 识别网上报.xlsx
```

Three commands share the same parsers and report model:

- **`gmeta run`** — full pipeline from FASTQ to reports.
- **`gmeta report`** — build a report from existing profiler outputs (no re-run).
- **`gmeta net build`** — the surveillance submission workbook, with optional
  per-species genome coverage from raw reads and reference genomes.

## Installation at a glance

```bash
pixi install               # full environment: kraken2/bracken/fastp/bowtie2/sylph/…
pip install gmeta          # Python 3.12 package only (tools from PATH)
```

See [Quick start](installation/quick-start.md) and [Databases](installation/databases.md).

## Example

```bash
# Surveillance submission from kraken2 kreports, with genome coverage
gmeta net build kraken/*.report \
  --reads-dir raw_reads \
  --manifest ref_genome_manifest.csv \
  -o 识别网上报.xlsx --split-dir result/
```

The output workbook carries the template-exact 混合样本 sheet plus an 审核明细
review sheet with latin names, TaxIDs, accessions and depth metrics.
