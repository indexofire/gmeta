# 文件格式

## gmeta 解析的输入

### kraken2 kreport（制表符分隔，无表头）

```text
100.00  100000  0     R  1    root
 40.00  40000   40000 S  9606   Homo sapiens
 30.00  29500   500   G  641     Vibrio
 25.00  25000   25000 S  662       Vibrio cholerae
```

列序：`百分比 | clade 读段数（含子层级） | 直接读段数 | rank 代码 | taxid |
缩进名称`。**名称缩进就是树**——种按缩进深度与最近属祖先配对。R/U 行给出
分类/未分类总数。也接受空格对齐和无 taxid 的变体。

### bracken

表头 `name tax_id taxonomy_lvl kraken_assigned_reads added_reads
new_est_reads fraction_total_reads`；仅种行（`S`）。fraction 列是百分数
（总和 ~100）；量纲自动探测，0..1 输入也能解析。

### centrifuge 原生 report

`name taxID taxRank genomeSize numReads numUniqueReads abundance`，无表头。
taxRank 为 `species`/`genus` 的行进入识别网适配层；abundance 列（0..1）优先于
读数重算。

### kaiju2table

表头 `file percent reads taxon_id taxon_name`；taxon_name 可以是 "; " 连接的
谱系。用 `-l species` 生成（属级表用 `-l genus`）。

### MetaPhlAn profile

`#clade_name NCBI_tax_id relative_abundance [additional_species]` 行
（`g__…` 属、`s__…` 种）。`rel_ab_w_read_stats` 增加的
`estimated_number_of_reads_from_the_clade` 按表头名解析。

### KMCP profile（17 列）

`ref percentage coverage score chunksFrac chunksRelDepth chunksRelDepthStd
reads ureads hicureads refsize refname taxid rank taxname taxpath
taxpathsn`。需要 taxid（+taxname 或 refname）；按参考的行按 taxid 聚合。

### sylph profile

表头含 `Genome_file`、`Adjusted_ANI`、`Eff_cov`、`Taxonomic_abundance`。

## gmeta 写出的输出

### 识别网工作簿（xlsx）

混合样本 sheet：样本名称 | 属中文名 | 属序列数 | 属相对丰度 | 种中文名 |
种序列数 | 种基因组覆盖度 | 种相对丰度——丰度为 `48.23%` 字符串，覆盖度为
0–100 浮点数，样本名称仅在每个样本首行填写。
审核明细 sheet：样本名称 | 属拉丁名 | 属中文名 | 种拉丁名 | 种中文名 | TaxID |
属序列数 | 种序列数 | 种相对丰度 | accession | 参考基因组 | 参考基因组长度 |
平均测序深度 | 覆盖度1x(%)。

### 报告文件

`.json` —— [MetaReport](json-contract.zh.md)。`.html` —— 自包含 Jinja2 模板。
`.xlsx` —— 检测概览 + 物种检出 sheet。`.pdf` —— HTML 模板的 WeasyPrint 渲染。

### 下载脚本（db fetch）

每个目标一个 `fetch-<tool>.sh`：`set -euo pipefail`、可续传下载函数、安装到
`$GMETA_DB_DIR`、目录结构校验，外加 `run_all.sh`。
