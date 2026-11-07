# Layers

## Module map

```text
src/gmeta/
├── cli.py                 click: run / report / net build / db list+fetch
├── config.py              GMETA_* env, DB_DIR, pixi-aware which()
├── dbfetch.py             download-script generation (db fetch)
├── engine/_env.py         require_bin / run_checked / run_to_file
├── analysis/
│   ├── kraken2.py         kreport parse (tree) + kraken2/bracken exec
│   ├── centrifuge.py      centrifuge exec → kreport path
│   ├── kaiju.py           kaiju + kaiju2table exec
│   ├── metaphlan.py       metaphlan exec
│   ├── kmcp.py            kmcp search + profile exec
│   ├── sylph.py           sylph exec (ported from gside)
│   ├── profilers.py       third-party format parsers + sniffing
│   ├── qc.py / host.py    fastp, bowtie2 host removal
│   └── coverage.py        minimap2+samtools 种基因组覆盖度
└── report/
    ├── models.py          pydantic MetaReport + build_report
    ├── network.py         识别网 rows/sheets + adapters
    ├── priority.py        重点病原标注
    └── render/excel/pdf   HTML(Jinja2)/Excel(openpyxl)/PDF(weasyprint)
```

## Data flow

```text
FASTQ ─run→ fastp → bowtie2 → profile_<tool>() ─┐
file  ─report/net→ detect_profiler() → parse ───┤
                                                ├→ AbundanceProfile / KreportSummary
                                                │        │
                                                │        ├→ MetaReport (pydantic)
                                                │        │     └→ JSON/HTML/Excel/PDF
                                                └→ resolve_reference + coverage_for_species
                                                         └→ NetworkRow → 识别网.xlsx
```

Two normalised shapes feed everything downstream:

- **`KreportSummary`** (kraken2/centrifuge trees) — indentation tree with
  real clade counts at every rank.
- **`AbundanceProfile`** (table-based profilers) — species rows + optional
  genus rows; `network.build_rows_from_profile` pairs them, aggregating
  genus counts when the tool provides none.

## Binary resolution

`config.which()` searches `GMETA_PIXI_BIN` → the repo's pixi env → the
user-level pixi env → `PATH`. `engine.require_bin` turns a miss into a
RuntimeError with the exact `pixi add` hint; every executor uses it, so the
error wording is identical across tools.
