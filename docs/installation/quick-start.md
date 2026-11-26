# Quick start

## 1. Install

```bash
cd gmeta
pixi install
```

## 2. Check the tool resolution

```bash
pixi run gmeta -V
pixi run gmeta db list     # shows kraken2/sylph database locations
```

## 3. Full pipeline from FASTQ

```bash
pixi run gmeta run sample_R1.fq.gz sample_R2.fq.gz \
  -s SAMPLE-001 \
  -D /data/db/kraken2 \
  --host-index /data/db/hg19 \
  -f json -f html -f xlsx -f pdf \
  -O gmeta-out/SAMPLE-001
```

Pipeline: fastp QC → bowtie2 host removal → kraken2 + bracken → reports in
every selected format (`<sample>.report.<fmt>`), result JSON on stdout.

## 4. Report from existing results

Already ran kraken2 elsewhere? Skip the compute:

```bash
pixi run gmeta report -s SAMPLE-001 \
  --kreport kreport.txt --bracken bracken.txt --fastp-json fastp.json \
  -o SAMPLE-001.report.html        # format from extension
```

## 5. Surveillance submission workbook

```bash
pixi run gmeta net build kraken/*.report \
  --reads-dir raw_reads \
  --manifest ref_genome_manifest.csv \
  -J 4 -t 4 \
  -o 识别网上报.xlsx --split-dir result/
```

- 混合样本 sheet: the template-exact eight columns (属/种中文名、序列数、
  相对丰度、种基因组覆盖度), 样本名称 only on each sample's first row.
- 审核明细 sheet: latin names, TaxID, accession, reference path, mean depth,
  plus a 覆盖度状态 column (`已计算` / `缺参考基因组` / `缺reads` / …).
- `--split-dir`: one single-sheet workbook per sample (sample id on every row).
- Coming from step 3? Point it at the run's artifact — the sample id comes
  from the directory: `gmeta net build gmeta-out/SAMPLE-001/pipeline/kreport.txt …`

[More on the 识别网 export →](../usage/network.md)

## Full walkthrough: `gmeta run` → 识别网 workbook (with coverage loop)

Using `1_R1.fq.gz` / `1_R2.fq.gz` (sample id `1`, kraken2):

```bash
# 0) one-time setup: DB root outside the code tree; check/provision databases
export GMETA_DB_DIR=/data/gmeta-db
gmeta db list                                  # ready / what is missing per tool
gmeta db fetch kraken2 -O scripts/ && bash scripts/fetch-kraken2.sh

# 1) profile: fastp QC → (optional) host removal → kraken2 + bracken
gmeta run 1_R1.fq.gz 1_R2.fq.gz -s 1 -m kraken2 \
  -D "$GMETA_DB_DIR/kraken2" -O gmeta-out/1 -t 8
# artifacts: gmeta-out/1/pipeline/kreport.txt / bracken.txt / fastp.json

# 2) first workbook pass: report + missing-reference list
gmeta net build gmeta-out/1/pipeline/kreport.txt \
  --reads-dir . --ref-dir "$GMETA_DB_DIR/refs" \
  -o 1.xlsx --details coverage_details.tsv \
  --missing-refs-out missing_refs.tsv -t 8

# 3) if missing_refs.tsv has rows: fetch references, then re-run (skip if empty)
gmeta db fetch refs --missing-refs missing_refs.tsv -O scripts/
bash scripts/fetch-refs.sh
gmeta net build gmeta-out/1/pipeline/kreport.txt \
  --reads-dir . \
  --ref-dir "$GMETA_DB_DIR/refs" --manifest "$GMETA_DB_DIR/refs/manifest.csv" \
  -o 1.xlsx --details coverage_details.tsv -t 8
```

Rules that matter:

- **The sample id must match the reads prefix** (`-s 1` ↔ `1_R1.fq.gz`);
  `net build` derives it from `gmeta-out/<sample>/pipeline/`, or use
  `--sample-id 1` to override.
- Read discovery is automatic: `_R1/_R2`, `_1/_2`, `.1/.2`, single-end; on a
  miss the terminal lists similar filenames in the reads dir.
- Check `coverage: X/N row(s) filled` in the terminal and the 覆盖度状态 column
  on the 审核明细 sheet: `已计算` ok; `缺reads` fix naming/`--sample-id`;
  `缺参考基因组` run step 3; `未请求（无 --reads-dir）` add the flag.
- 1× breadth is saturating: 90%+ is normal for mid/high-abundance taxa — read
  it together with 平均测序深度; use `--min-depths 5,10,50` for stricter metrics.

Batch: `gmeta run -S samples.tsv -m kraken2 -J 4` (one dir per sample);
`gmeta net build gmeta-out/*/pipeline/kreport.txt -J 4` (concurrent samples).
