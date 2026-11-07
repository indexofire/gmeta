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
  -o 识别网上报.xlsx --split-dir result/
```

- 混合样本 sheet: the template-exact eight columns (属/种中文名、序列数、
  相对丰度、种基因组覆盖度), 样本名称 only on each sample's first row.
- 审核明细 sheet: latin names, TaxID, accession, reference path, mean depth.
- `--split-dir`: one single-sheet workbook per sample (sample id on every row).

[More on the 识别网 export →](../usage/network.md)
