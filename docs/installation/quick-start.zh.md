# 快速开始

## 1. 安装

```bash
cd gmeta
pixi install
```

## 2. 检查工具解析

```bash
pixi run gmeta -V
pixi run gmeta db list     # 显示 kraken2/sylph 数据库位置
```

## 3. 从 FASTQ 跑全流程

```bash
pixi run gmeta run sample_R1.fq.gz sample_R2.fq.gz \
  -s SAMPLE-001 \
  -D /data/db/kraken2 \
  --host-index /data/db/hg19 \
  -f json -f html -f xlsx -f pdf \
  -O gmeta-out/SAMPLE-001
```

流程：fastp 质控 → bowtie2 去宿主 → kraken2 + bracken → 按所选格式出报告
（`<sample>.report.<fmt>`），结果 JSON 打到 stdout。

## 4. 从已有结果出报告

已经在别处跑过 kraken2？直接导入：

```bash
pixi run gmeta report -s SAMPLE-001 \
  --kreport kreport.txt --bracken bracken.txt --fastp-json fastp.json \
  -o SAMPLE-001.report.html        # 格式按扩展名分发
```

## 5. 监测上报工作簿

```bash
pixi run gmeta net build kraken/*.report \
  --reads-dir raw_reads \
  --manifest ref_genome_manifest.csv \
  -o 识别网上报.xlsx --split-dir result/
```

- 混合样本 sheet：与模板一致的 8 列（属/种中文名、序列数、相对丰度、种基因组覆盖度），
  样本名称仅在每个样本首行填写。
- 审核明细 sheet：拉丁名、TaxID、accession、参考基因组路径、平均深度。
- `--split-dir`：每样本一个单 sheet 工作簿（每行填样本名）。

[识别网导出详解 →](../usage/network.zh.md)
