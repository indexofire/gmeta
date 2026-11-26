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

### From `gmeta run` to the workbook — one command

`gmeta run` keeps its profiler artifacts under `<outdir>/<sample>/pipeline/`
(`kreport.txt`, `bracken.txt`, `fastp.json`, …). `net build` recognises that
layout: the sample id comes from the directory, so the run output feeds the
workbook directly and reads are found by the sample id.

With `--auto-refs` the whole reference workflow collapses into the same
command: missing species references are downloaded via the NCBI Datasets CLI
before coverage runs (references already on disk are reused).

```bash
# 1) profile one sample (kraken2 + bracken)
gmeta run 1_R1.fq.gz 1_R2.fq.gz -s 1 -m kraken2 \
  -D /data/db/kraken2 -O gmeta-out/1 -t 8

# 2) workbook + coverage in one go (fetches missing refs automatically)
gmeta net build gmeta-out/1/pipeline/kreport.txt \
  --reads-dir . --auto-refs \
  --ref-dir "$GMETA_DB_DIR/refs" \
  -o 1.xlsx --details coverage_details.tsv -t 8
```

Notes:

- `--auto-refs` needs the NCBI Datasets CLI (`datasets`) on PATH — install
  it with `conda install -c conda-forge ncbi-datasets-cli` or the standalone
  binary (see [Databases](../installation/databases.md)). Without network
  access, fall back to the manual
  loop: run once with `--missing-refs-out`, then
  `gmeta db fetch refs --missing-refs …` and re-run.
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

**Kingdom filtering** — 识别网 is a 致病菌 (bacterial) network, so only
bacteria are reported by default. The kraken2 kreport path classifies each
species exactly from its ancestor chain (Bacteria 2 / Archaea 2157 /
Eukaryota 2759 / Viruses 10239). Table-based profilers have no taxonomy:
kaiju carries the lineage, other formats fall back to a name heuristic
(names ending in `virus`/`phage`/`viroid` are viruses); unknown rows are
treated as bacterial. Combine kingdoms with `+` (`--kingdom viruses+bacteria`)
or use `--kingdom all` to disable the filter entirely.

**Host taxa are filtered out** before ranking: `Homo sapiens` (TaxID 9606)
never appears in the submission table even when host reads dominate the
sample. Extend `HOST_TAXIDS` in `src/gmeta/report/network.py` for animal
hosts (e.g. 10090 mouse).

### Reading 种基因组覆盖度

Coverage breadth is a **saturating** metric, not a linear abundance proxy:
with tens of millions of reads, a species at a few percent abundance
already reaches tens of × mean depth, so 90–100% at the 1× threshold is
normal for mid/high-abundance taxa in deep mNGS. Judge results together
with the 审核明细 columns:

| Observation | Reading |
| --- | --- |
| 90%+ coverage with mean depth ≫1× | expected — depth saturates breadth |
| 90%+ coverage with mean depth <1× | investigate reference/genome size |
| ~90%+ even for 0.1% abundance | possible cross-mapping among close relatives; re-check with `--per-species` |
| Same magnitude as the legacy workflow | normal |

For more discrimination, record stricter thresholds with
`--min-depths 5,10,50` — 5×/10× breadth separates taxa better than 1×.

### Performance

`-J/--jobs` runs samples concurrently (the cost is coverage: minimap2 +
samtools per sample); `-t/--threads` stays per tool invocation. Aim for
`-J × -t ≈ CPU cores`. Each concurrent sample also holds a temporary BAM
roughly the size of its combined reference set, so keep `-J` moderate on
small disks.

When a profiler has no genus rows (kmcp, kaiju without the genus table),
genus counts are aggregated from that genus' species rows — the honest
estimate the format allows.

Missing references leave the coverage cell blank and print the taxids; the
rows themselves are still emitted.

## Options

| Flag | Meaning |
| --- | --- |
| `--kingdom` | taxonomic kingdom(s) to report, `+`-joined: `bacteria` (default — 识别网 is a bacterial surveillance network), `archaea`, `eukaryota`, `viruses`, or `all`; e.g. `--kingdom viruses+bacteria` |
| `--profiler` | force the format (auto/kraken2/bracken/centrifuge/kaiju/metaphlan/kmcp/sylph) |
| `--sample-id` | override the derived sample id (single input; fixes reads matching when the artifact path lacks the id) |
| `-J/--jobs` | concurrent samples (default 1; coverage is the bottleneck) |
| `-t/--threads` | threads per minimap2/samtools invocation |
| `--kaiju-genus` | kaiju2table genus table for real genus counts |
| `--top` | species rows per sample (default 10) |
| `--reads-dir` + `--reads-pattern` | raw reads for coverage; when the pattern misses, FASTQs starting with the sample id are auto-detected (mates paired by `_R1/_R2`, `_1/_2`, `.1/.2`, single-end ok) |
| `--auto-refs` | download missing references via the NCBI Datasets CLI before coverage (one command; cached references are reused) |
| `--manifest` / `--ref-dir` | reference genomes |
| `--missing-refs-out` | TSV of species with no resolvable reference (sample, taxid, latin name, reads) |
| `--split-dir` | one workbook per sample |
| `--details` | extra coverage TSV |
| `--per-species` | independent per-reference alignment (exact, slower) |
| `--min-depths` | coverage thresholds (default 1,5,10) |
| `--preset` | minimap2 read preset: sr / map-ont / map-pb |
