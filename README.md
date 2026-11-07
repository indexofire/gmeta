# gmeta

宏基因组（mNGS）分析与监测报告工具 — 从测序数据到国家致病菌识别网监测报告、突发疫情宏基因组测序报告。

`gmeta` 与 [gside](../gside)（单菌物种鉴定）、[gmlst](../gmlst)（基因组分型）同一工具家族：纯 Python CLI（Python 3.12），外部生信工具经 pixi（bioconda）管理，风格与输出结构保持一致。

## 功能

- **mNGS 全流程** `gmeta run`：fastp 质控 → bowtie2 去宿主 → 物种丰度分析，支持 **6 种分析软件**：kraken2+bracken、sylph、centrifuge、kaiju、MetaPhlAn、KMCP
- **结果解析出报告** `gmeta report`：直接导入已有分析结果（同样 6 种软件的 8 种格式），无需重跑
- **识别网上报** `gmeta net build`：分析结果 → 国家致病菌识别网"混合样本"模板格式（属/种中文名、序列数、相对丰度、种基因组覆盖度），支持批量样本、按样本拆分、覆盖度自动计算、**格式自动嗅探**
- **数据库管理** `gmeta db fetch`：生成各数据库的可续传下载脚本（不代跑，URL 可审查），`gmeta db list` 检查数据库状态
- **报告输出**：JSON（结构化）、HTML（网页）、Excel（上报数据交换）、PDF（正式文档），同一数据模型四种渲染
- **重点病原标注**：内置监测重点病原列表（甲类/乙类传染病、监测重点、突发疫情防控、呼吸道病原），检出自动标注中文名与类别
- **MAGs 分析**（规划中）：bin 质量评估、物种归属、基因组汇总

### 支持的 mNGS 分析软件

| 软件 | 执行（`run -m`） | 导入格式 | 识别网属计数来源 |
|---|:---:|---|---|
| kraken2 (+bracken) | ✅ | kreport / bracken 表 | 树形解析，真实 clade 计数 |
| sylph | ✅ | profile TSV | 种读数聚合 |
| centrifuge | ✅ | 原生 report 或 kreport | 原生属级行 |
| kaiju | ✅ | kaiju2table（种级+属级） | 属级表 |
| MetaPhlAn | ✅ | profile（v3/v4） | `g__` 属级行 |
| KMCP | ✅ | compute profile TSV | 种读数聚合 |

## 安装

```bash
pixi install          # 解析 conda + pypi 依赖（kraken2/bracken/fastp/bowtie2/sylph/minimap2）
pixi run test         # dev 环境跑测试
```

## 快速上手

### 全流程（从 FASTQ 开始）

```bash
gmeta run sample_R1.fq.gz sample_R2.fq.gz \
  -s SAMPLE-001 \                     # 样本编号
  -D /data/db/kraken2 \               # kraken2+bracken 数据库
  --host-index /data/db/hg19 \        # 宿主 bowtie2 索引（可省略，跳过去宿主）
  -f json -f html -f xlsx -f pdf \
  -O gmeta-out/SAMPLE-001
```

### 从已有结果出报告

```bash
# JSON 到 stdout
gmeta report -s SAMPLE-001 --bracken bracken.txt --kreport kreport.txt --fastp-json fastp.json

# 四种格式，按扩展名分发
gmeta report -s SAMPLE-001 --bracken bracken.txt -o SAMPLE-001.report.html
gmeta report -s SAMPLE-001 --bracken bracken.txt -o SAMPLE-001.report.xlsx
gmeta report -s SAMPLE-001 --bracken bracken.txt -o SAMPLE-001.report.pdf
```

### 识别网上报（国家致病菌识别网"混合样本"模板）

```bash
# 自动嗅探输入格式（kraken2/bracken/centrifuge/kaiju/metaphlan/kmcp/sylph 可混用）
gmeta net build results/*.{report,tsv,txt} -o 识别网上报.xlsx --split-dir result/ --top 10

# 指定软件类型 / kaiju 补充属级表
gmeta net build sample.kmcp.tsv --profiler kmcp -o 识别网上报.xlsx
gmeta net build sample.species.tsv --kaiju-genus sample.genus.tsv -o 识别网上报.xlsx

# 含种基因组覆盖度：提供原始 reads + 参考基因组 manifest（CSV：
# accession,species_taxid,organism_taxid,scientific_name,file_path）
gmeta net build kraken/*.report \
  --reads-dir raw_reads --reads-pattern "{sample}_R{pair}.fastq.gz" \
  --manifest ref_genome_manifest.csv \
  -o 识别网上报.xlsx --split-dir result/ --details coverage_details.tsv
```

- 输出工作簿含两个 sheet：**混合样本**（模板 8 列：样本名称/属中文名/属序列数/属相对丰度/种中文名/种序列数/种基因组覆盖度/种相对丰度）+ **审核明细**（拉丁名、TaxID、accession、参考基因组、平均深度等）
- `--split-dir` 按样本另存单样本工作簿（每行填样本名，与上报要求一致）
- 覆盖度默认合并参考一次比对（快）；`--per-species` 逐参考独立比对（精确、慢）
- 长读段用 `--preset map-ont` / `--preset map-pb`
- 属/种中文名取自内置映射表（`src/gmeta/data/*.tsv|csv`），未收录回退拉丁名
- 表格式软件（centrifuge/kaiju/metaphlan/kmcp）的属序列数：有属级行时直接采信，否则由种读数聚合；相对丰度优先采信软件自带数值

### 数据库准备

```bash
gmeta db list                       # 查看数据库位置与状态
gmeta db fetch                      # 生成全部数据库下载脚本 → ./db-fetch/
gmeta db fetch kraken2 kmcp -O scripts/ --db-root /data/db   # 数据库默认: <repo>/data/db（仓库）或 ~/.local/share/gmeta/db（pip 安装），GMETA_DB_DIR 可覆盖
bash scripts/fetch-kraken2.sh       # 审查 URL 后自行运行（可断点续传）
bash scripts/run_all.sh             # 或按顺序全部执行
```

kmcp 预建库在 OneDrive/网盘（无稳定 wget 地址），其脚本会自动下载 NCBI
taxdump 并给出手动下载指引；其余数据库（minikraken2、centrifuge 索引、kaiju
nr_ezh、metaphlan 标记库、sylph sketch、GRCh38 宿主索引）脚本直接下载。

## 文档

完整文档（中英双语）：`pixi run -e dev docs` 本地预览，或
https://indexofire.github.io/gmeta/

## 报告判读

- 丰度：物种读段占比（bracken 估计读数 / sylph 分类丰度）
- 置信度：high ≥10%、medium ≥1%、low <1%（sylph：ANI ≥95% 为 high、≥90% 为 medium）
- 重点病原：命中内置监测列表时在报告中单独提示（含中文名与监测类别）
- 结果需结合临床与流行病学信息判读，不作为唯一诊断依据

## 项目结构

```
src/gmeta/
├── cli.py            # click CLI：run / report / db
├── config.py         # GMETA_* 环境变量、pixi-aware 二进制定位
├── engine/_env.py    # require_bin + run_checked（与 gside 同源）
├── analysis/         # kraken2/bracken、sylph（移植自 gside meta 层）+ fastp、bowtie2
├── report/           # pydantic 数据模型、优先病原标注、JSON/HTML/Excel/PDF 渲染
└── templates/        # Jinja2 报告模板（HTML 与 PDF 共用）
```

## 开发

```bash
pixi run -e dev check     # ruff lint + format 检查
pixi run -e dev fix       # 自动修复
pixi run -e dev typecheck # pyright
pixi run -e dev test      # pytest
pixi run -e dev cov       # pytest + coverage
```

## License

MIT
