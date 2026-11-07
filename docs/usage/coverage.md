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
- **Read length matters**: minimap2 `-x sr` needs ≥50 bp reads; ONT/PacBio
  data must pass `--preset map-ont` / `--preset map-pb`.
- **Reference resolution order**: manifest by `species_taxid` →
  `{accession}*.fna` in `--ref-dir` → manifest `file_path` →
  `{taxid}*.fna` glob. Unresolved taxids leave coverage blank.
- `--min-depths 1,5,10` controls the thresholds recorded on the 审核明细
  sheet; the submission sheet always shows 1×.
