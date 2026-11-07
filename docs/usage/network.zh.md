# 识别网导出

`gmeta net build` 把分析软件的结果转换成国家致病菌识别网"混合样本"上报工作簿。

## 输出

每个工作簿两个 sheet：

**混合样本** —— 与模板一致的 8 列：

| 样本名称 | 属中文名 | 属序列数 | 属相对丰度 | 种中文名 | 种序列数 | 种基因组覆盖度 | 种相对丰度 |
| --- | --- | --- | --- | --- | --- | --- | --- |

样本名称仅在每个样本首行填写（模板风格）；丰度是百分比字符串（`48.23%`），
覆盖度是 0–100 浮点数。

**审核明细** —— 拉丁名、TaxID、accession、参考基因组路径/长度、平均深度、
1x 覆盖度：上报 sheet 刻意省略的全部信息。

## 示例

```bash
# kraken2 kreport，自动识别格式
gmeta net build kraken/*.report -o 识别网上报.xlsx --split-dir result/

# 多软件混用——每个文件独立嗅探
gmeta net build kraken/a.report centrifuge/b.txt kmcp/c.tsv -o 识别网上报.xlsx

# 含种基因组覆盖度
gmeta net build kraken/*.report \
  --reads-dir raw_reads --manifest ref_genome_manifest.csv \
  -o 识别网上报.xlsx --split-dir result/ --details coverage_details.tsv
```

## 各软件的语义

| 软件 | 属序列数来源 | 种相对丰度来源 |
| --- | --- | --- |
| kraken2 kreport | 属 clade 行（真实计数） | kreport 百分比 |
| centrifuge 原生 | report 中的属行 | abundance 列 |
| kaiju（+`--kaiju-genus`） | 属级 kaiju2table | percent 列 |
| metaphlan | `g__` 行 | relative_abundance |
| kmcp | 种读数聚合（按参考行格式） | percentage（聚合后） |

软件没有属级行时（kmcp、未附属表的 kaiju），属计数由该属的种读数聚合——
该格式下最诚实的估计。

参考基因组缺失时覆盖度单元格留空并打印 taxid；行本身照常输出。

## 参数

| 参数 | 含义 |
| --- | --- |
| `--profiler` | 强制指定格式（auto/kraken2/bracken/centrifuge/kaiju/metaphlan/kmcp/sylph） |
| `--kaiju-genus` | kaiju2table 属级表，提供真实属计数 |
| `--top` | 每样本物种行数（默认 10） |
| `--reads-dir` + `--reads-pattern` | 覆盖度用的原始 reads |
| `--manifest` / `--ref-dir` | 参考基因组 |
| `--split-dir` | 每样本一个工作簿 |
| `--details` | 额外的覆盖度 TSV |
| `--per-species` | 每个参考独立比对（精确、慢） |
| `--min-depths` | 覆盖度阈值（默认 1,5,10） |
| `--preset` | minimap2 读段预设：sr / map-ont / map-pb |
