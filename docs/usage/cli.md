# CLI reference

Global flags (before the subcommand): `-V/--version` (`-J` for JSON),
`-v/--verbose`, `-q/--quiet`, `-h/--help`. Every command accepts
`-t/--threads` (default 4).

## run

Full pipeline from FASTQ: fastp QC → bowtie2 host removal (optional) →
profiling → reports.

```bash
# single sample
gmeta run sample_R1.fq.gz sample_R2.fq.gz \
  -s SAMPLE-001 -m kraken2 \
  -D /data/db/kraken2 --host-index /data/db/host/grch38 \
  -f json -f html -f xlsx -f pdf \
  -O gmeta-out/SAMPLE-001 -t 16

# batch: manifest (sample_id<TAB>r1[<TAB>r2] per line) with 4 concurrent samples
gmeta run -S samples.tsv -m kraken2 -D /data/db/kraken2 -J 4 -O gmeta-out

# batch: positional reads grouped by mate markers (A_R1 A_R2 B_R1 B_R2 → A, B)
gmeta run A_R1.fq A_R2.fq B_R1.fq B_R2.fq -m kmcp -D /data/db
```

Batch runs write per-sample directories (`<outdir>/<sample>/…`) and emit one
JSON line per sample on stdout (order preserved even with `-J`); a failed
sample yields `{"sample": …, "error": …}` without aborting the batch.

| Flag | Meaning |
| --- | --- |
| `-s/--sample-id` | sample identifier (single-sample runs; batches derive ids from filenames) |
| `-S/--samples` | batch manifest: `sample_id<TAB>reads [<TAB>reads2]` per line |
| `-J/--jobs` | concurrent samples in batch runs (default 1) |
| `-m/--method` | kraken2 (default) / sylph / centrifuge / kaiju / metaphlan / kmcp |
| `-D/--db-dir` | profiler database root; default `$GMETA_DB_DIR` |
| `--host-index` | bowtie2 host index prefix; omit to skip host removal |
| `-O/--outdir` | output directory (single: gmeta-out/<sample-id>; batch: gmeta-out/<sample>/*) |
| `-f/--format` | report formats, repeatable: json html xlsx pdf (default json+html) |
| `--sample-type` `--platform` `--lab` `--operator` `--sequencing-date` | metadata recorded in the report |

Artifacts land in `<outdir>/pipeline/` (kreport.txt, bracken.txt,
centrifuge.tsv, kaiju.*.tsv, profile.tsv …) so reports can cite them.

## report

Build a report from existing results — no re-run.

```bash
gmeta report -s SAMPLE-001 --kreport k.txt --bracken b.txt --fastp-json f.json
gmeta report -s SAMPLE-001 --metaphlan profile.txt -o SAMPLE-1.report.html
```

| Flag | Meaning |
| --- | --- |
| `--kreport` / `--bracken` | kraken2 outputs (either alone works) |
| `--fastp-json` | QC metrics for the report |
| `--sylph-profile` | sylph profile TSV |
| `--centrifuge` | centrifuge native report |
| `--kaiju` / `--kaiju-genus` | kaiju2table species / genus tables |
| `--metaphlan` | MetaPhlAn profile |
| `--kmcp` | KMCP profile TSV |
| `-o/--output` | output file; format from extension (.json/.html/.xlsx/.pdf), default JSON to stdout |
| `--top` / `--min-fraction` | row filtering (default 50 / 0.0) |

## net build

识别网 submission workbook — see [识别网 export](network.md).

## db

```bash
gmeta db list                    # database locations + state
gmeta db fetch [TARGETS]...      # generate download scripts (not executed)
```

Fetch targets: `kraken2 centrifuge kaiju metaphlan kmcp sylph taxdump host`,
or `all`. Options: `-O/--out-dir` (default `db-fetch`), `--db-root`
(install root baked into the scripts). See [Databases](../installation/databases.md).
