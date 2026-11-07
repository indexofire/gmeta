# 分层设计

## 模块地图

```text
src/gmeta/
├── cli.py                 click 命令：run / report / net build / db list+fetch
├── config.py              GMETA_* 环境变量、DB_DIR、pixi 感知的 which()
├── dbfetch.py             下载脚本生成（db fetch）
├── engine/_env.py         require_bin / run_checked / run_to_file
├── analysis/
│   ├── kraken2.py         kreport 解析（树形）+ kraken2/bracken 执行
│   ├── centrifuge.py      centrifuge 执行 → kreport 路径
│   ├── kaiju.py           kaiju + kaiju2table 执行
│   ├── metaphlan.py       metaphlan 执行
│   ├── kmcp.py            kmcp search + profile 执行
│   ├── sylph.py           sylph 执行（自 gside 移植）
│   ├── profilers.py       第三方格式解析器 + 嗅探
│   ├── qc.py / host.py    fastp、bowtie2 去宿主
│   └── coverage.py        minimap2+samtools 种基因组覆盖度
└── report/
    ├── models.py          pydantic MetaReport + build_report
    ├── network.py         识别网行/表 + 适配层
    ├── priority.py        重点病原标注
    └── render/excel/pdf   HTML(Jinja2)/Excel(openpyxl)/PDF(weasyprint)
```

## 数据流

```text
FASTQ ─run→ fastp → bowtie2 → profile_<tool>() ─┐
文件  ─report/net→ detect_profiler() → 解析 ───┤
                                                ├→ AbundanceProfile / KreportSummary
                                                │        │
                                                │        ├→ MetaReport (pydantic)
                                                │        │     └→ JSON/HTML/Excel/PDF
                                                └→ resolve_reference + coverage_for_species
                                                         └→ NetworkRow → 识别网.xlsx
```

两个规范化形状供给下游一切：

- **`KreportSummary`**（kraken2/centrifuge 树）——带缩进层级的树，各 rank 有
  真实 clade 计数。
- **`AbundanceProfile`**（表格式软件）——物种行 + 可选属行；
  `network.build_rows_from_profile` 负责配对，软件没有属数据时聚合出属计数。

## 二进制定位

`config.which()` 依次搜索 `GMETA_PIXI_BIN` → 仓库自身 pixi 环境 → 用户级
pixi 环境 → `PATH`。`engine.require_bin` 把未找到变成带精确 `pixi add`
提示的 RuntimeError；所有执行器都走它，错误措辞跨工具一致。
