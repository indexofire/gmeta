# gmeta 文档

`gmeta` 是一个用于宏基因组（mNGS）谱分析与监测报告的 Python CLI。它可以从 FASTQ 运行
fastp 质控 → 去宿主 → kraken2/bracken（或 sylph）全流程，可以导入七种第三方分析软件的
结果，并生成国家致病菌识别网上报工作簿与 JSON/HTML/Excel/PDF 报告。

## 从这里开始

| 我想… | 阅读 |
| --- | --- |
| 安装并跑第一个样本 | [快速开始](installation/quick-start.zh.md) |
| 查所有 CLI 参数 | [CLI 参考](usage/cli.zh.md) |
| 生成识别网上报工作簿 | [识别网导出](usage/network.zh.md) |
| 导入 centrifuge/kaiju/metaphlan/kmcp 结果 | [支持的分析软件](usage/profilers.zh.md) |
| 理解种基因组覆盖度计算 | [覆盖度计算](usage/coverage.zh.md) |
| 准备 kraken2/sylph/参考基因组数据库 | [数据库](installation/databases.zh.md) |
| 查文件格式规范 | [文件格式](reference/formats.zh.md) |
| 安全消费 JSON 输出 | [JSON 契约](reference/json-contract.zh.md) |

## gmeta 做什么

```text
FASTQ reads ──────── fastp 质控 → bowtie2 去宿主 ───────┐
已有结果 ─────────── kraken2 / bracken / centrifuge ────┼──→ 物种丰度谱
                     kaiju / metaphlan / kmcp / sylph ───┘        │
                                                                   ├─→ JSON / HTML / Excel / PDF 报告
原始 reads + 参考基因组 ── minimap2 + samtools ──→ 种基因组覆盖度 ─┴─→ 识别网上报.xlsx
```

三个命令共享同一套解析器与报告模型：

- **`gmeta run`** —— 从 FASTQ 到报告的完整流程。
- **`gmeta report`** —— 从已有分析结果直接出报告（不重跑）。
- **`gmeta net build`** —— 监测上报工作簿，可用原始 reads + 参考基因组计算种基因组覆盖度。

## 安装概览

```bash
pixi install               # 完整环境：kraken2/bracken/fastp/bowtie2/sylph/…
pip install gmeta          # 仅 Python 3.12 包（外部工具取自 PATH）
```

见[快速开始](installation/quick-start.zh.md)与[数据库](installation/databases.zh.md)。

## 示例

```bash
# 从 kraken2 kreport 生成含基因组覆盖度的监测上报
gmeta net build kraken/*.report \
  --reads-dir raw_reads \
  --manifest ref_genome_manifest.csv \
  -o 识别网上报.xlsx --split-dir result/
```

输出工作簿包含与模板一致的混合样本 sheet，外加审核明细 sheet（拉丁名、TaxID、
accession、深度指标）。
