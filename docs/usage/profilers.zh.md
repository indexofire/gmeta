# 支持的分析软件

六个分析软件，每个都支持**导入**和**执行**。导入接受下列格式；执行
（`gmeta run -m …`）从 pixi 环境调用外部工具。

## kraken2 + bracken

- **导入**：kreport（树形格式）和/或 bracken 种级表。
- **执行**：`gmeta run -m kraken2` 先跑 kraken2 再跑 bracken；bracken 的读长
  取自数据库的 `databaseXXXmers.kmer_distrib` 文件名。
- kreport 列序很关键：`百分比 | clade 读段数 | 直接读段数 | rank | taxid |
  缩进名称`。gmeta 通过名称缩进把种配到属——真实的属 clade 计数。

## centrifuge

- **导入**：原生 report（`name taxID taxRank genomeSize numReads
  numUniqueReads abundance`）或任意 kraken 风格 kreport（如
  `centrifuge-kreport` 的输出）。
- **执行**：`gmeta run -m centrifuge` 先分类，再用 `centrifuge-kreport` 转换，
  复用 kraken2 的 kreport 路径——识别网导出获得同样的树形精确属配对。

## kaiju

- **导入**：`kaiju2table` 输出（`file percent reads taxon_id taxon_name`）。
  种级表作为 profile 传入；`--kaiju-genus` 补充真实属计数。谱系名称
  （"Bacteria; Escherichia; Escherichia coli"）会被解析出属提示。
- **执行**：`gmeta run -m kaiju` 先跑 kaiju，再对种级和属级分别跑 kaiju2table。

## metaphlan

- **导入**：含 `#clade_name NCBI_tax_id relative_abundance …` 行的 profile；
  `rel_ab_w_read_stats` 格式还会填充种序列数（估计读段）。
- **执行**：`gmeta run -m metaphlan` 运行 `metaphlan -t rel_ab_w_read_stats`，
  `--bowtie2db $DB_DIR/metaphlan`。

## kmcp

- **导入**：`kmcp profile` 的 17 列 TSV；需要 `taxid`/`rank`/`taxname` 列
  （数据库带 taxid 映射构建时存在）。按 taxid 聚合按参考的行。
- **执行**：`gmeta run -m kmcp` 先 `kmcp search`（按官方推荐用单端模式提高
  敏感度）再 `kmcp profile --level species`。需要 `$DB_DIR/taxdump` 下的
  NCBI taxdump。
- 注意：KMCP 的百分比按参考计；总和请对照审核明细 sheet 核查。

## sylph

- **导入**：profile TSV（`Genome_file`、`Adjusted_ANI`、`Taxonomic_abundance`）。
- **执行**：`gmeta run -m sylph` 运行 sketch + profile；置信度按 ANI 分档
  （high ≥95%、medium ≥90%）。

## 格式嗅探

`net build` 自动识别每个输入文件的格式；`--profiler` 强制指定。嗅探器区分
带表头（kaiju、metaphlan、kmcp、bracken、sylph）与无表头布局（centrifuge 的
名称打头、kraken2 的百分比打头 kreport）。
