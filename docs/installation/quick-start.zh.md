# 快速开始

## 1. 安装

```bash
cd gmeta
pixi install
```

## 2. 检查工具解析

```bash
pixi run gmeta -V
pixi run gmeta db list     # 显示 kraken2/sylph 数据库位置
```

## 3. 从 FASTQ 跑全流程

```bash
pixi run gmeta run sample_R1.fq.gz sample_R2.fq.gz \
  -s SAMPLE-001 \
  -D /data/db/kraken2 \
  --host-index /data/db/hg19 \
  -f json -f html -f xlsx -f pdf \
  -O gmeta-out/SAMPLE-001
```

流程：fastp 质控 → bowtie2 去宿主 → kraken2 + bracken → 按所选格式出报告
（`<sample>.report.<fmt>`），结果 JSON 打到 stdout。

## 4. 从已有结果出报告

已经在别处跑过 kraken2？直接导入：

```bash
pixi run gmeta report -s SAMPLE-001 \
  --kreport kreport.txt --bracken bracken.txt --fastp-json fastp.json \
  -o SAMPLE-001.report.html        # 格式按扩展名分发
```

## 5. 监测上报工作簿

```bash
pixi run gmeta net build kraken/*.report \
  --reads-dir raw_reads \
  --manifest ref_genome_manifest.csv \
  -J 4 -t 4 \
  -o 识别网上报.xlsx --split-dir result/
```

- 混合样本 sheet：与模板一致的 8 列（属/种中文名、序列数、相对丰度、种基因组覆盖度），
  样本名称仅在每个样本首行填写。
- 审核明细 sheet：拉丁名、TaxID、accession、参考基因组路径、平均深度，
  外加覆盖度状态列（`已计算` / `缺参考基因组` / `缺reads` / …）。
- `--split-dir`：每样本一个单 sheet 工作簿（每行填样本名）。
- 从第 3 步延续？直接传 run 的产物即可，样本号取自目录：
  `gmeta net build gmeta-out/SAMPLE-001/pipeline/kreport.txt …`

[识别网导出详解 →](../usage/network.zh.md)

## 完整工作流：`gmeta run` → 识别网上报（含覆盖度闭环）

以 `1_R1.fq.gz` / `1_R2.fq.gz`（样本号 `1`，kraken2）为例：

```bash
# 0) 一次性准备：数据库根放到数据盘（不在代码目录里），检查/补齐数据库
export GMETA_DB_DIR=/data/gmeta-db
gmeta db list                                  # 每个目标：ready / 缺什么
gmeta db fetch kraken2 -O scripts/ && bash scripts/fetch-kraken2.sh

# 1) 分析：fastp 质控 →（可选）去宿主 → kraken2 + bracken
gmeta run 1_R1.fq.gz 1_R2.fq.gz -s 1 -m kraken2 \
  -D "$GMETA_DB_DIR/kraken2" -O gmeta-out/1 -t 8
# 产物：gmeta-out/1/pipeline/kreport.txt / bracken.txt / fastp.json

# 2) 首轮上报：生成工作簿 + 缺失参考清单
gmeta net build gmeta-out/1/pipeline/kreport.txt \
  --reads-dir . --ref-dir "$GMETA_DB_DIR/refs" \
  -o 1.xlsx --details coverage_details.tsv \
  --missing-refs-out missing_refs.tsv -t 8

# 3) 若 missing_refs.tsv 有内容：补下载参考后重跑（无缺失则跳过）
gmeta db fetch refs --missing-refs missing_refs.tsv -O scripts/
bash scripts/fetch-refs.sh
gmeta net build gmeta-out/1/pipeline/kreport.txt \
  --reads-dir . \
  --ref-dir "$GMETA_DB_DIR/refs" --manifest "$GMETA_DB_DIR/refs/manifest.csv" \
  -o 1.xlsx --details coverage_details.tsv -t 8
```

关键规则：

- **样本号必须与 reads 文件名前缀一致**（`-s 1` ↔ `1_R1.fq.gz`）；`net build`
  能从 `gmeta-out/<样本号>/pipeline/` 推出样本号，也可用 `--sample-id 1` 覆盖。
- reads 命名自动识别：`_R1/_R2`、`_1/_2`、`.1/.2`、单端均可；都不匹配时终端会列出
  目录中相似文件名。
- 终端结尾看 `coverage: X/N row(s) filled`；打开审核明细看"覆盖度状态"列：
  `已计算` 成功；`缺reads` 查命名/`--sample-id`；`缺参考基因组` 执行第 3 步；
  `未请求（无 --reads-dir）` 补参数。
- 1× 覆盖度是饱和指标：中高丰度物种 90%+ 属正常，结合"平均测序深度"判读；
  更严格阈值用 `--min-depths 5,10,50`。

批量：`gmeta run -S samples.tsv -m kraken2 -J 4`（每样本一个目录）；
`gmeta net build gmeta-out/*/pipeline/kreport.txt -J 4`（跨样本并行覆盖度）。
