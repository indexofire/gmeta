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

### 从 `gmeta run` 到上报工作簿——一条命令

`gmeta run` 的分析产物保存在 `<outdir>/<sample>/pipeline/`（`kreport.txt`、
`bracken.txt`、`fastp.json` 等）。`net build` 识别这个目录结构：样本号取自
样本目录，run 的产物可直接生成工作簿，reads 也按样本号自动匹配。

加上 `--auto-refs` 后，整个参考基因组准备流程合并进同一条命令：缺失的物种
参考通过 NCBI Datasets CLI 在计算覆盖度前自动下载（已存在的直接复用）。

```bash
# 1) 单样本分析（kraken2 + bracken）
gmeta run 1_R1.fq.gz 1_R2.fq.gz -s 1 -m kraken2 \
  -D /data/db/kraken2 -O gmeta-out/1 -t 8

# 2) 一条命令出工作簿 + 覆盖度（缺参考自动下载）
gmeta net build gmeta-out/1/pipeline/kreport.txt \
  --reads-dir . --auto-refs \
  --ref-dir "$GMETA_DB_DIR/refs" \
  -o 1.xlsx --details coverage_details.tsv -t 8
```

注意：

- `gmeta run` 会把准确的样本号写进 `<outdir>/<sample>/pipeline/sample.json`；
  `net build` 优先读取它，因此输出目录名与样本号不同（如
  `-O output2 -s 26AS311`）时也能正确匹配 reads。`--sample-id` 仍是显式覆盖。
- 样本号匹配不到、但 reads 目录里只有**一组** FASTQ 时，自动采用该组并打印提示；
  有多组时列出组名，用 `--sample-id`/`--reads-pattern` 指定。
- `--auto-refs` 需要 PATH 中有 NCBI Datasets CLI（`datasets`；安装：
  `conda install -c conda-forge ncbi-datasets-cli` 或独立二进制，见
  [数据库](../installation/databases.zh.md)）。无网络时退回手动闭环：先跑一次
  `--missing-refs-out`，再 `gmeta db fetch refs --missing-refs …` 后重跑。
- 旧版本（不含 pipeline 目录推断）请先复制成样本名文件：
  `cp gmeta-out/1/pipeline/kreport.txt gmeta-out/1/1.kreport`，再传该路径。
- `-D` 需要完整 kraken2 库：`hash.k2d/taxo.k2d/opts.k2d` **加**
  `databaseXXXmers.kmer_distrib`（bracken 用）。缺库时用
  `gmeta db fetch kraken2` 生成下载脚本。
- `--host-index` 可选；省略时宿主 reads 留在样本里，但不会进入上报表行。

## 各软件的语义

| 软件 | 属序列数来源 | 种相对丰度来源 |
| --- | --- | --- |
| kraken2 kreport | 属 clade 行（真实计数） | kreport 百分比 |
| centrifuge 原生 | report 中的属行 | abundance 列 |
| kaiju（+`--kaiju-genus`） | 属级 kaiju2table | percent 列 |
| metaphlan | `g__` 行 | relative_abundance |
| kmcp | 种读数聚合（按参考行格式） | percentage（聚合后） |

**分类界过滤**——识别网是致病菌（细菌）监测网，默认只报告细菌。kraken2
kreport 路径通过祖先链精确判定（Bacteria 2 / Archaea 2157 / Eukaryota 2759 /
Viruses 10239）。表格式软件没有分类树：kaiju 带谱系可用；其余按名称启发式
（以 `virus`/`phage`/`viroid` 结尾视为病毒）；无法判定的按细菌处理。多个界用
`+` 组合（`--kingdom viruses+bacteria`），`--kingdom all` 完全关闭过滤。

**宿主类群在排序前被过滤**：即使宿主 reads 占绝对多数，`Homo sapiens`
（TaxID 9606）也不会出现在上报表中。动物宿主（如 10090 小鼠）可扩展
`src/gmeta/report/network.py` 里的 `HOST_TAXIDS`。

### 如何解读种基因组覆盖度

覆盖度是**饱和型指标**，不是丰度的线性反映：千万级 reads 下，占比几个百分点的
物种平均深度就能到几十×，1× 阈值下中高丰度物种普遍 90~100%，属于正常。结合
审核明细列判断：

| 现象 | 解读 |
| --- | --- |
| 覆盖度 90%+ 且平均深度 ≫1× | 正常——深度足够必然饱和 |
| 覆盖度 90%+ 但平均深度 <1× | 检查参考基因组是否完整/基因组大小 |
| 0.1% 丰度也 90%+ | 可能近缘种交叉比对；用 `--per-species` 复核 |
| 与旧流程结果量级一致 | 正常 |

需要更强区分度时用 `--min-depths 5,10,50` 记录更高阈值——5×/10× 覆盖率比 1×
更能拉开物种差异。

### 性能

`-J/--jobs` 跨样本并行（成本在覆盖度：每样本一套 minimap2 + samtools）；
`-t/--threads` 是单次工具调用的线程数。建议 `-J × -t ≈ CPU 核数`。每个并发
样本会持有约等于其合并参考集大小的临时 BAM，磁盘小时 `-J` 不宜开大。

软件没有属级行时（kmcp、未附属表的 kaiju），属计数由该属的种读数聚合——
该格式下最诚实的估计。

参考基因组缺失时覆盖度单元格留空并打印 taxid；行本身照常输出。

## 参数

| 参数 | 含义 |
| --- | --- |
| `--kingdom` | 报告的分类界，`+` 连接多个：`bacteria`（默认——识别网是致病菌监测网）、`archaea`、`eukaryota`、`viruses`、`all`；如 `--kingdom viruses+bacteria` |
| `--profiler` | 强制指定格式（auto/kraken2/bracken/centrifuge/kaiju/metaphlan/kmcp/sylph） |
| `--sample-id` | 覆盖推导的样本号（仅单输入；当产物路径里没有样本号时用它对齐 reads） |
| `-J/--jobs` | 并发的样本数（默认 1；覆盖度计算是瓶颈） |
| `-t/--threads` | 每次 minimap2/samtools 调用的线程数 |
| `--kaiju-genus` | kaiju2table 属级表，提供真实属计数 |
| `--top` | 每样本物种行数（默认 10） |
| `--reads-dir` + `--reads-pattern` | 覆盖度用的原始 reads；pattern 未命中时自动按样本名前缀探测（`_R1/_R2`、`_1/_2`、`.1/.2` 配对，单端亦可） |
| `--auto-refs` | 计算覆盖度前自动下载缺失参考（NCBI Datasets CLI；已存在的直接复用，一条命令完成） |
| `--manifest` / `--ref-dir` | 参考基因组 |
| `--missing-refs-out` | 输出缺参考物种清单 TSV（样本、taxid、拉丁名、读数） |
| `--split-dir` | 每样本一个工作簿 |
| `--details` | 额外的覆盖度 TSV |
| `--per-species` | 每个参考独立比对（精确、慢） |
| `--min-depths` | 覆盖度阈值（默认 1,5,10） |
| `--preset` | minimap2 读段预设：sr / map-ont / map-pb |
