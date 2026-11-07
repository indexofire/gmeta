# CLI 参考

全局参数（子命令之前）：`-V/--version`（`-J` 输出 JSON）、`-v/--verbose`、
`-q/--quiet`、`-h/--help`。所有命令接受 `-t/--threads`（默认 4）。

## run

从 FASTQ 跑全流程：fastp 质控 → bowtie2 去宿主（可选）→ 物种分析 → 报告。

```bash
# 单样本
gmeta run sample_R1.fq.gz sample_R2.fq.gz \
  -s SAMPLE-001 -m kraken2 \
  -D /data/db/kraken2 --host-index /data/db/host/grch38 \
  -f json -f html -f xlsx -f pdf \
  -O gmeta-out/SAMPLE-001 -t 16

# 批量：清单（每行 sample_id<TAB>r1[<TAB>r2]），4 个样本并行
gmeta run -S samples.tsv -m kraken2 -D /data/db/kraken2 -J 4 -O gmeta-out

# 批量：按 mate 标记分组的位置参数（A_R1 A_R2 B_R1 B_R2 → A、B 两个样本）
gmeta run A_R1.fq A_R2.fq B_R1.fq B_R2.fq -m kmcp -D /data/db
```

批量运行按样本写目录（`<outdir>/<sample>/…`），stdout 每样本一行 JSON
（`-J` 并行也保持清单顺序）；单样本失败输出 `{"sample": …, "error": …}`，
不中断整批。

| 参数 | 含义 |
| --- | --- |
| `-s/--sample-id` | 样本编号（单样本运行；批量模式从文件名推导） |
| `-S/--samples` | 批量清单：每行 `sample_id<TAB>reads [<TAB>reads2]` |
| `-J/--jobs` | 批量运行的并行样本数（默认 1） |
| `-m/--method` | kraken2（默认）/ sylph / centrifuge / kaiju / metaphlan / kmcp |
| `-D/--db-dir` | 分析软件数据库根目录；默认 `$GMETA_DB_DIR` |
| `--host-index` | bowtie2 宿主索引前缀；省略则跳过去宿主 |
| `-O/--outdir` | 输出目录（单样本：gmeta-out/<sample-id>；批量：gmeta-out/<sample>/*） |
| `-f/--format` | 报告格式，可重复：json html xlsx pdf（默认 json+html） |
| `--sample-type` `--platform` `--lab` `--operator` `--sequencing-date` | 写入报告的元数据 |

中间产物保存在 `<outdir>/pipeline/`（kreport.txt、bracken.txt、centrifuge.tsv、
kaiju.*.tsv、profile.tsv …），供报告引用与复查。

## report

从已有结果出报告——不重跑。

```bash
gmeta report -s SAMPLE-001 --kreport k.txt --bracken b.txt --fastp-json f.json
gmeta report -s SAMPLE-001 --metaphlan profile.txt -o SAMPLE-1.report.html
```

| 参数 | 含义 |
| --- | --- |
| `--kreport` / `--bracken` | kraken2 输出（单独提供也可以） |
| `--fastp-json` | 报告用的 QC 指标 |
| `--sylph-profile` | sylph profile TSV |
| `--centrifuge` | centrifuge 原生 report |
| `--kaiju` / `--kaiju-genus` | kaiju2table 种级 / 属级表 |
| `--metaphlan` | MetaPhlAn profile |
| `--kmcp` | KMCP profile TSV |
| `-o/--output` | 输出文件；格式按扩展名（.json/.html/.xlsx/.pdf），默认 JSON 到 stdout |
| `--top` / `--min-fraction` | 行过滤（默认 50 / 0.0） |

## net build

识别网上报工作簿——见[识别网导出](network.zh.md)。

## db

```bash
gmeta db list                    # 数据库位置与状态
gmeta db fetch [TARGETS]...      # 生成下载脚本（不执行）
```

fetch 目标：`kraken2 centrifuge kaiju metaphlan kmcp sylph taxdump host` 或
`all`。选项：`-O/--out-dir`（默认 `db-fetch`）、`--db-root`（写进脚本的安装根目录）。
见[数据库](../installation/databases.zh.md)。
