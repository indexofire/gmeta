# Testing

```bash
pixi run -e dev test             # whole suite
pixi run -e dev cov              # with coverage
pixi run -e dev pytest tests/unit -q
pixi run -e dev pytest tests/integration -q
```

## Layout

```text
tests/
├── conftest.py                 kreport/bracken/fastp fixtures (real layouts)
├── unit/
│   ├── test_kraken2_parse.py   kreport tree + bracken parsing
│   ├── test_profilers.py       centrifuge/kaiju/metaphlan/kmcp parsers + sniffing
│   ├── test_executors.py       executors with fake binaries
│   ├── test_coverage_parse.py  manifest/refs/reads helpers
│   ├── test_network*.py        识别网 rows, sheets, adapters, CLI
│   ├── test_report_*.py        MetaReport assembly + rendering
│   ├── test_dbfetch.py         download-script generation
│   └── test_cli*.py            command surfaces
└── integration/
    └── test_coverage_integration.py   real minimap2+samtools (auto-skipped off-path)
```

## Conventions

- **Fixtures embed real layouts** — the kreport fixture keeps kraken2's
  exact column order and indentation so parser regressions surface fast.
- **External tools are faked with shell scripts** on `GMETA_PIXI_BIN`
  (`test_executors.py`): this exercises the real binary resolution and
  subprocess plumbing hermetically.
- **Integration tests skip themselves** when binaries are missing, so the
  suite runs on any machine with `pixi run -e dev test`.
- Cross-validation tests pin the equivalence of the kraken2 tree path and
  the table adapter path for 识别网 output — keep them passing when either
  path changes.
