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

## Semantics per profiler

| Profiler | 属序列数 source | 种相对丰度 source |
| --- | --- | --- |
| kraken2 kreport | genus clade row (real counts) | kreport percentage |
| centrifuge native | genus rows in the report | abundance column |
| kaiju (+`--kaiju-genus`) | genus kaiju2table | percent column |
| metaphlan | `g__` rows | relative_abundance |
| kmcp | species aggregation (per-reference format) | percentage (aggregated) |

When a profiler has no genus rows (kmcp, kaiju without the genus table),
genus counts are aggregated from that genus' species rows — the honest
estimate the format allows.

Missing references leave the coverage cell blank and print the taxids; the
rows themselves are still emitted.

## Options

| Flag | Meaning |
| --- | --- |
| `--profiler` | force the format (auto/kraken2/bracken/centrifuge/kaiju/metaphlan/kmcp/sylph) |
| `--kaiju-genus` | kaiju2table genus table for real genus counts |
| `--top` | species rows per sample (default 10) |
| `--reads-dir` + `--reads-pattern` | raw reads for coverage |
| `--manifest` / `--ref-dir` | reference genomes |
| `--split-dir` | one workbook per sample |
| `--details` | extra coverage TSV |
| `--per-species` | independent per-reference alignment (exact, slower) |
| `--min-depths` | coverage thresholds (default 1,5,10) |
| `--preset` | minimap2 read preset: sr / map-ont / map-pb |
