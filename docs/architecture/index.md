# Architecture

gmeta is organised in three layers, mirroring the gside/gspec/gmlst tool
family:

```text
cli.py ────────────── click commands: run / report / net / db
analysis/ ─────────── profilers + executors + pre-processing
report/ ───────────── data model, formats, 识别网 exporter
```

See [Layers](layers.md) for the module map and data flow, and the
[JSON contract](../reference/json-contract.md) for stable output.
