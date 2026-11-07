# 覆盖度计算

识别网工作簿中的种基因组覆盖度 = 原始 reads 以 ≥1× 深度覆盖物种参考基因组的
比例（minimap2 + samtools，移植自原来的 `calculate_coverage.py` 流程）。

## 流程

```text
top-N 物种 → 参考基因组 FASTA（manifest / ref-dir）
reads（原始数据，未质控——与旧流程一致）
   → minimap2 -ax <preset> -c … | samtools sort  → BAM
   → samtools depth -a（全部位置，含零深度）
   → 每物种：平均深度 + 1x/5x/10x 覆盖比例
```

深度行单遍流式聚合——不用 numpy 数组，内存占用与基因组大小无关。

## 合并模式 vs 逐参考模式

默认（**合并**）：每样本把参考基因组拼接成一条参考、只比对一次——多物种样本
约快 10 倍。多物种可比到多处相同的 reads 只会计入一个最优匹配。

`--per-species`：每个参考独立比对——严格独立的估计，慢约 N 倍。

## 需要知道的细节

- **用的是原始 FASTQ**（`--reads-dir`），不是质控/去宿主后的文件——与旧版
  `calculate_coverage.py` 的口径一致，跨批次可比。
- **读长有影响**：minimap2 `-x sr` 需要 ≥50 bp 读段；ONT/PacBio 数据必须传
  `--preset map-ont` / `--preset map-pb`。
- **参考解析顺序**：manifest 按 `species_taxid` → `--ref-dir` 里
  `{accession}*.fna` → manifest `file_path` → `{taxid}*.fna` 通配。解析不到的
  taxid 覆盖度留空。
- `--min-depths 1,5,10` 控制审核明细 sheet 记录的阈值；上报 sheet 固定用 1×。
