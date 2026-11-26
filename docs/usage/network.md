# 识别网 export

`gmeta net build` turns profiler output into the 国家致病菌识别网
"混合样本" submission workbook.

## The output

Two sheets per workbook:

**混合样本** — the template-exact eight columns:

| 样本名称 | 属中文名 | 属序列数 | 属相对丰度 | 种中文名 | 种序列数 | 种基因组覆盖度 | 种相对丰度 |
| --- | --- | --- | --- | --- | --- | --- | --- |

样本名称 is written only on each sample's first row (template style);
abundances are percent strings (`48.23%`), coverage is a 0–100 float.

**审核明细** — latin names, TaxID, accession, reference path/length, mean
depth, 1x coverage: everything the submission sheet intentionally omits.

## Examples

```bash
# kraken2 kreports, auto-detected
gmeta net build kraken/*.report -o 识别网上报.xlsx --split-dir result/

# mixed tools in one batch — each file sniffed independently
gmeta net build kraken/a.report centrifuge/b.txt kmcp/c.tsv -o 识别网上报.xlsx

# with 种基因组覆盖度
gmeta net build kraken/*.report \
  --reads-dir raw_reads --manifest ref_genome_manifest.csv \
  -o 识别网上报.xlsx --split-dir result/ --details coverage_details.tsv
```

### From `gmeta run` to the workbook

`gmeta run` keeps its profiler artifacts under `<outdir>/<sample>/pipeline/`
(`kreport.txt`, `bracken.txt`, `fastp.json`, …). `net build` recognises that
layout: the sample id comes from the directory, so the run output feeds the
workbook directly and reads are found by the sample id.

```bash
# 1) profile one sample (kraken2 + bracken)
gmeta run 1_R1.fq.gz 1_R2.fq.gz -s 1 -m kraken2 \
  -D /data/db/kraken2 -O gmeta-out/1 -t 8

# 2) surveillance workbook from the run's kreport (sample id inferred as "1")
gmeta net build gmeta-out/1/pipeline/kreport.txt \
  --reads-dir . \
  --manifest ref_genome_manifest.csv --ref-dir ref_genomes \
  -o 1.xlsx --details coverage_details.tsv --missing-refs-out missing_refs.tsv -t 8
```

Notes:

- On releases without the pipeline-layout inference, copy the artifact to a
  sample-named file first: `cp gmeta-out/1/pipeline/kreport.txt gmeta-out/1/1.kreport`
  and pass that path instead.
- `-D` needs a complete kraken2 DB: `hash.k2d/taxo.k2d/opts.k2d` **plus**
  `databaseXXXmers.kmer_distrib` (bracken). `gmeta db fetch kraken2` writes the
  download script when the DB is missing.
- `--host-index` is optional; without it host reads stay in the sample but are
  filtered from the surveillance rows anyway.

## Semantics per profiler

| Profiler | 属序列数 source | 种相对丰度 source |
| --- | --- | --- |
| kraken2 kreport | genus clade row (real counts) | kreport percentage |
| centrifuge native | genus rows in the report | abundance column |
| kaiju (+`--kaiju-genus`) | genus kaiju2table | percent column |
| metaphlan | `g__` rows | relative_abundance |
| kmcp | species aggregation (per-reference format) | percentage (aggregated) |

**Host taxa are filtered out** before ranking: `Homo sapiens` (TaxID 9606)
never appears in the submission table even when host reads dominate the
sample. Extend `HOST_TAXIDS` in `src/gmeta/report/network.py` for animal
hosts (e.g. 10090 mouse).

When a profiler has no genus rows (kmcp, kaiju without the genus table),
genus counts are aggregated from that genus' species rows — the honest
estimate the format allows.

Missing references leave the coverage cell blank and print the taxids; the
rows themselves are still emitted.

## Options

| Flag | Meaning |
| --- | --- |
| `--profiler` | force the format (auto/kraken2/bracken/centrifuge/kaiju/metaphlan/kmcp/sylph) |
| `--sample-id` | override the derived sample id (single input; fixes reads matching when the artifact path lacks the id) |
| `-J/--jobs` | concurrent samples (default 1; coverage is the bottleneck) |
| `-t/--threads` | threads per minimap2/samtools invocation |
| `--kaiju-genus` | kaiju2table genus table for real genus counts |
| `--top` | species rows per sample (default 10) |
| `--reads-dir` + `--reads-pattern` | raw reads for coverage; when the pattern misses, FASTQs starting with the sample id are auto-detected (mates paired by `_R1/_R2`, `_1/_2`, `.1/.2`, single-end ok) |
| `--manifest` / `--ref-dir` | reference genomes |
| `--missing-refs-out` | TSV of species with no resolvable reference (sample, taxid, latin name, reads) |
| `--split-dir` | one workbook per sample |
| `--details` | extra coverage TSV |
| `--per-species` | independent per-reference alignment (exact, slower) |
| `--min-depths` | coverage thresholds (default 1,5,10) |
| `--preset` | minimap2 read preset: sr / map-ont / map-pb |
