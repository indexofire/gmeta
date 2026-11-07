# Changelog

本项目所有显著变更记录于此。
格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.1.0] - 2026-11-07

首个发行版：宏基因组（mNGS）分析与监测报告工具，自 gside 的 meta 层整体迁移并扩展。

### Changed

- 数据库默认根目录不再指向包内路径：仓库检出用 `<repo>/data/db`（已 gitignore），pip 安装用 XDG 数据目录（`~/.local/share/gmeta/db`）——gmeta 的数据库全部是外部下载的大文件，`site-packages` 不可写也不该存放。`$GMETA_DB_DIR` 仍最优先。移除了从未实际生效的 `GMETA_DATA_DIR`（中文名表本就随包分发）。
- `gmeta db list` 重写：覆盖全部 8 个数据库目标（kraken2/centrifuge/kaiju/metaphlan/kmcp/sylph/taxdump/host），每个探针直接复用执行器的 resolver（就绪 = 分析软件会真正接受该路径，含 bracken kmer_distrib、kaiju names.dmp、kmcp taxdump 等伴生文件校验）；默认 Rich 表格输出，`-f json` 提供稳定机器契约。新增 `gmeta/dbstate.py`。
- `resolve_sylph_db` 从 `profile_sylph` 中抽出复用；kmcp 的 taxdump 查找支持兄弟目录布局（`$DB_ROOT/kmcp` + `$DB_ROOT/taxdump`）；kraken2 缺库错误提示统一指向 `gmeta db fetch`。
- `gmeta run` 批量模式（自 gside `scan --meta` 体系移植）：`-S/--samples` 清单（`sample_id<TAB>reads [<TAB>reads2]`，表头可选、# 注释、重复 id 拒绝）、位置参数多样本按 mate 标记分组（`A_R1 A_R2 B_R1 B_R2` → 两样本）、`-J/--jobs` 线程池并行（输出保持清单顺序）；批量每样本一个输出目录，stdout 每样本一行 JSON，单样本失败不中断整批。`-s/--sample-id` 变为可选（单样本可从文件名推导）。新增 `gmeta/samples.py`。
- `gmeta run` 执行器扩展：centrifuge（比对 + `centrifuge-kreport` 转 kreport，复用树形精确路径）、kaiju（比对 + 种/属双 rank kaiju2table）、MetaPhlAn（`-t rel_ab_w_read_stats`，种序列数可用）、KMCP（官方推荐的 search 单端模式 + profile --level species）。`-m/--method` 现支持 kraken2/sylph/centrifuge/kaiju/metaphlan/kmcp。
- `gmeta db fetch`：生成数据库下载 shell 脚本（不代执行），目标 kraken2/centrifuge/kaiju/metaphlan/kmcp/sylph/taxdump/host，含可续传下载函数、目录校验、run_all.sh；kmcp 预建库为 OneDrive/网盘发布，脚本自动下载 taxdump 并指引手动步骤。
- `engine/_env.run_to_file`：stdout 流式落盘执行（centrifuge 系工具用）。
- sylph 下 fetch 脚本地址更新为官方预建库（gside 同源验证过的 googleapis 地址）。
- MetaPhlAn 解析器按表头名识别 `estimated_number_of_reads_from_the_clade` 列（rel_ab_w_read_stats），种序列数不再恒为 0。
- 第三方 mNGS 分析软件导入支持（解析+导出，不含执行）：Centrifuge（原生 report，属级行直接采信）、Kaiju（kaiju2table，可附属级表）、MetaPhlAn（v3/v4 profile）、KMCP（compute profile，按 taxid 聚合参考行）。
- `analysis/profilers.py`：统一 `AbundanceProfile` 规范化模型（物种/属丰度行）、四工具解析器、格式自动嗅探 `detect_profiler`（含 kraken2/bracken/sylph 共 7 种）。相对丰度优先采信软件自带数值（百分比/比例量纲按列总和自动判定），缺失时由读数重算。
- `report/network.py`：`build_rows_from_profile` 通用识别网适配层——表格式软件的属序列数优先用真实属级行，否则由种读数聚合；`profile_to_network_rows` 统一入口（kraken2 走树形精确路径，其余走适配层）。
- `gmeta net build` 输入扩展为任意支持格式（自动嗅探 / `--profiler` 强制指定 / `--kaiju-genus` 补属级数据）；`gmeta report` 新增 `--centrifuge/--kaiju/--metaphlan/--kmcp` 输入。
- 交叉验证：同一数据经 centrifuge 格式路径与 kraken2 kreport 树形路径生成识别网表，10/10 行一致。
- mkdocs 文档站（material + 中英双语）：安装/使用/识别网导出/分析软件/覆盖度/架构/格式规范/JSON 契约/开发指南。
- `gmeta net build`：国家致病菌识别网"混合样本"上报格式。整合原有 kraken2 结果转换脚本：kreport 属/种配对（缩进树解析）、属/种中文名映射（taxid 表 + 拉丁名表）、参考基因组 manifest 解析、minimap2+samtools 种基因组覆盖度计算（合并参考/逐参考两种模式，纯 Python 流式统计，无 numpy/pandas 依赖）、批量多样本工作簿 + 按样本拆分 + 审核明细 sheet。实测与旧流程输出逐行一致。
- 修正 kreport 解析的列序（col2=clade 读段数、col3=直接读段数），kreport 行新增缩进深度 `depth` 用于属种树配对。
- samtools/centrifuge/kaiju/metaphlan/kmcp 加入 pixi 依赖。
- 项目骨架：pixi + src 布局 + hatchling，与 gside/gspec/gmlst 工具家族风格统一。
- `analysis/`：kraken2+bracken 解析与执行、sylph 解析与执行（自 gside meta 层移植，kreport 解析扩展至全分类层级）、fastp 质控、bowtie2 去宿主。
- `report/`：pydantic 报告数据模型、重点病原标注（内置监测列表）、JSON/HTML/Excel/PDF 四种渲染（HTML 与 PDF 共用 Jinja2 模板）。
- `gmeta run`：FASTQ → fastp → 去宿主 → kraken2/bracken 或 sylph → 多格式报告。
- `gmeta report`：从已有 kreport/bracken/fastp/sylph 结果直接生成报告。
- `gmeta db list`：数据库位置与状态检查。
