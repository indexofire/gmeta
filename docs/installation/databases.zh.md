# 数据库

gmeta 的所有数据库都解析自同一个根目录。默认值按安装位置自适应：仓库检出用
`<repo>/data/db`（已 gitignore），pip 安装用 XDG 数据目录
（`~/.local/share/gmeta/db`）——数据库是几十 GB 的外部下载物，绝不放进包内。
用 `GMETA_DB_DIR` 或 `-D` 覆盖：

| 工具 | 期望路径 | 必需文件 |
| --- | --- | --- |
| kraken2 + bracken | `kraken2/` | `*.k2d` + `databaseXXXmers.kmer_distrib` |
| centrifuge | `centrifuge/` | `<prefix>.1.cf.index*` |
| kaiju | `kaiju/` | `nodes.dmp`、`names.dmp`、`*.fmi` |
| metaphlan | `metaphlan/` | `mpa_v*/` 或 `*.bt2l*` |
| kmcp | `kmcp/` | `*.uniki` + `taxid.map`（另需 `taxdump/` 含 `nodes.dmp`） |
| sylph | `sylph/` | `*.syldb` / `*.syl2db` |
| 去宿主 | `host/` | bowtie2 索引前缀（如 `grch38.1.bt2l`） |

检查解析结果：`gmeta db list` —— 一张覆盖全部 8 个目标的 Rich 表格（ready/missing
+ 精确缺失的文件）；`gmeta db list -f json` 是稳定的机器契约。每个探针调用的就是
执行器用的同一个 resolver，所以"ready"意味着分析软件真的会接受该路径——包括
bracken 的 `kmer_distrib`、kaiju 的 `names.dmp` 这类伴生文件。

## 下载脚本

数据库动辄几十 GB——`gmeta db fetch` **不直接下载**，而是生成带注释、可断点续传的
bash 脚本，由你审查后自行运行：

```bash
gmeta db fetch                    # 生成全部目标脚本 → ./db-fetch/
gmeta db fetch kraken2 kmcp -O scripts/ --db-root /data/db

bash scripts/fetch-kraken2.sh     # wget -c → 解压 → 校验目录结构
bash scripts/run_all.sh           # 或按顺序全部执行
```

脚本安装到 `$GMETA_DB_DIR`（或生成时 `--db-root` 指定的目录），并校验 gmeta
解析器期望的目录结构。

**kmcp 特殊**：其预建数据库发布在 OneDrive/奶牛快传（无稳定的 wget 地址）。
`fetch-kmcp.sh` 会自动下载 NCBI taxdump，然后给出手动下载数据库的说明退出——
手动步骤完成后重跑脚本即可完成校验。

URL 会随版本更新而变化；每个 URL 都放在脚本顶部的变量里，注释中附上游链接。

## 种基因组覆盖度的参考基因组

覆盖度计算需要物种参考基因组 FASTA + manifest CSV：

```csv
accession,species_taxid,organism_taxid,scientific_name,file_path
GCF_000025985.1,817,272559,Bacteroides fragilis NCTC 9343,refs/GCF_000025985.1.fna
```

相对 `file_path` 按 manifest 所在目录解析。没有 manifest 时，会在 `--ref-dir`
里搜 `{accession}*.fna` / `{taxid}*.fna`。

## 中文名映射表

`src/gmeta/data/` 内置监测用中文名表（`species_chinese_names.tsv`、
`genus_chinese_names.tsv`、`taxid_chinese_mapping.csv`）；未收录类群回退拉丁名。
映射表随包分发（体积小、与 gmeta 同版本管理）。扩展方式：编辑
`src/gmeta/data/*.tsv|csv` 后重装；未收录类群回退拉丁名。
