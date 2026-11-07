# JSON contract

`gmeta report` (and the stdout of `gmeta run`) emits a **MetaReport**.
Fields are stable; new optional fields may appear, existing ones do not
change meaning within a major version.

```json
{
  "schema_version": 1,
  "tool": "gmeta",
  "tool_version": "0.1.0",
  "generated_at": "2026-11-07T08:00:00+00:00",
  "sample": {
    "sample_id": "SAMPLE-001",
    "sample_type": null,
    "platform": null,
    "sequencing_date": null,
    "lab": null,
    "operator": null
  },
  "method": "kraken2_bracken",
  "database": "/data/db/kraken2",
  "qc": {
    "total_reads": 100000,
    "clean_reads": 96000,
    "total_bases": 15000000,
    "clean_bases": 14000000,
    "q30_rate": 0.95,
    "duplication_rate": 0.12,
    "host_reads": null,
    "host_rate": null,
    "classified_reads": 60000,
    "classified_fraction": 0.6
  },
  "taxa": [
    {
      "name": "Vibrio cholerae",
      "taxid": 662,
      "rank": "species",
      "reads": 25000,
      "fraction": 0.25,
      "ani": null,
      "confidence": "high",
      "priority": true,
      "priority_category": "霍乱弧菌（甲类传染病）"
    }
  ],
  "n_species": 4
}
```

## Fields

| Field | Notes |
| --- | --- |
| `method` | `kraken2_bracken` / `sylph_ani` / `centrifuge` / `kaiju` / `metaphlan` / `kmcp` |
| `qc.*` | `null` when the source did not provide the metric |
| `taxa[].reads` | estimated/species read count; `0` when the tool reports none (metaphlan rel_ab) |
| `taxa[].fraction` | always 0..1 |
| `taxa[].ani` | sylph only |
| `taxa[].confidence` | abundance bands: high ≥10%, medium ≥1%, low <1% (sylph: ANI ≥95% / ≥90%) |
| `taxa[].priority` | hit against the built-in surveillance pathogen list |

## MethodEnvelope

`profile_*()` functions return `{analysis_type, method, database, result}`
dataclass envelopes (the gside family contract); `result` carries the
method-specific detail (`top_species`, counts) and is **not** part of the
stable contract — consume MetaReport instead when stability matters.
