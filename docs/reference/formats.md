# File formats

## Inputs gmeta parses

### kraken2 kreport (tab-separated, no header)

```text
100.00  100000  0     R  1    root
 40.00  40000   40000 S  9606   Homo sapiens
 30.00  29500   500   G  641     Vibrio
 25.00  25000   25000 S  662       Vibrio cholerae
```

Columns: `percent | clade reads (children included) | direct reads | rank
code | taxid | indented name`. **The name indentation is the tree** —
species pair with their nearest genus ancestor by indent depth. R/U rows
supply classified/unclassified totals. Space-aligned reports and taxid-less
variants are also accepted.

### bracken

Header `name tax_id taxonomy_lvl kraken_assigned_reads added_reads
new_est_reads fraction_total_reads`; species rows (`S`) only. The fraction
column is a percentage (sums ~100); scale is auto-detected so 0..1 inputs
also parse.

### centrifuge native report

`name taxID taxRank genomeSize numReads numUniqueReads abundance`, no
header. taxRank `species`/`genus` rows feed the 识别网 adapter; the
abundance column (0..1) wins over reads-based recomputation.

### kaiju2table

Header `file percent reads taxon_id taxon_name`; taxon_name may be a
"; "-joined lineage. Generate with `-l species` (and `-l genus` for the
genus table).

### MetaPhlAn profile

`#clade_name NCBI_tax_id relative_abundance [additional_species]` rows
(`g__…` genus, `s__…` species). `rel_ab_w_read_stats` adds
`estimated_number_of_reads_from_the_clade`, parsed by header name.

### KMCP profile (17 columns)

`ref percentage coverage score chunksFrac chunksRelDepth chunksRelDepthStd
reads ureads hicureads refsize refname taxid rank taxname taxpath
taxpathsn`. Requires taxid (+taxname or refname); per-reference rows are
aggregated by taxid.

### sylph profile

Header includes `Genome_file`, `Adjusted_ANI`, `Eff_cov`,
`Taxonomic_abundance`.

## Outputs gmeta writes

### 识别网 workbook (xlsx)

Sheet 混合样本: 样本名称 | 属中文名 | 属序列数 | 属相对丰度 | 种中文名 |
种序列数 | 种基因组覆盖度 | 种相对丰度 — abundances as `48.23%` strings,
coverage as 0–100 floats, 样本名称 only on each sample's first row.
Sheet 审核明细: 样本名称 | 属拉丁名 | 属中文名 | 种拉丁名 | 种中文名 | TaxID |
属序列数 | 种序列数 | 种相对丰度 | accession | 参考基因组 | 参考基因组长度 |
平均测序深度 | 覆盖度1x(%).

### Report files

`.json` — [MetaReport](json-contract.md). `.html` — self-contained Jinja2
template. `.xlsx` — 检测概览 + 物种检出 sheets. `.pdf` — WeasyPrint render
of the HTML template.

### fetch scripts (db fetch)

One `fetch-<tool>.sh` per target: `set -euo pipefail`, resumable
download helper, install under `$GMETA_DB_DIR`, layout verification, plus
`run_all.sh`.
