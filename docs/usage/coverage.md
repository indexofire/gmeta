# Coverage

种基因组覆盖度 in the 识别网 workbook = percentage of a species' reference
genome covered by raw reads at ≥1× depth (minimap2 + samtools, ported from
the original `calculate_coverage.py` workflow).

## Pipeline

```text
top-N species → reference FASTAs (manifest / ref-dir)
reads (raw, pre-QC — same as the legacy workflow)
   → minimap2 -ax <preset> -c … | samtools sort  → BAM
   → samtools depth -a (every position, zero-depth included)
   → per-species: mean depth + % covered at 1x/5x/10x
```

Depth lines are aggregated in one streaming pass — no numpy arrays, memory
stays flat regardless of genome size.

## Combined vs per-species

Default (**combined**): one concatenated reference per sample, one
alignment — ~10× faster for multi-species samples. Reads mapping equally
well to several species are assigned to one best match only.

`--per-species`: one alignment per reference — strictly independent
estimates, ~N× slower.

## Details worth knowing

- **Reads are the raw FASTQs** (`--reads-dir`), not the QC/host-removed
  files — matching the legacy `calculate_coverage.py` contract, so
  coverage numbers remain comparable across batches.
- **Read discovery is forgiving**: the `--reads-pattern` is tried first
  (`{sample}_R{pair}.fastq.gz` by default, gz/plain variants); on a miss,
  any FASTQ starting with the sample id is auto-detected and mates are
  paired by `_R1/_R2`, `_1/_2`, `.1/.2` markers (single-end accepted).
- **Every row carries a 覆盖度状态** on the 审核明细 sheet (`已计算` /
  `缺参考基因组` / `缺reads` / `未请求（无 --reads-dir）` / `覆盖度计算失败`),
  so an empty coverage cell always has a visible reason. `--missing-refs-out`
  exports the species lacking references for follow-up downloads.

## Reading the values

Breadth at 1× is **saturating**: a species at a few percent of a deep mNGS
run already has tens of × mean depth, so 90–100% coverage is expected for
mid/high-abundance taxa — it is not a linear abundance measure. Use the
审核明细 columns together:

- `平均测序深度` — high depth explains high breadth; breadth ≫90% with mean
  depth <1× is worth investigating.
- `覆盖度1x(%)` — the submission value.
- `--min-depths 5,10,50` records stricter thresholds in the details TSV;
  5×/10× breadth discriminates taxa better than 1×.
- `--per-species` re-checks suspicious cases where cross-mapping among close
  relatives may inflate breadth.
- **Read length matters**: minimap2 `-x sr` needs ≥50 bp reads; ONT/PacBio
  data must pass `--preset map-ont` / `--preset map-pb`.
- **Reference resolution order**: manifest by `species_taxid` →
  `{accession}*.fna` in `--ref-dir` → manifest `file_path` →
  `{taxid}*.fna` glob. Unresolved taxids leave coverage blank.
- `--min-depths 1,5,10` controls the thresholds recorded on the 审核明细
  sheet; the submission sheet always shows 1×.
