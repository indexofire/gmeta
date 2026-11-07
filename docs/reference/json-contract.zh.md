# JSON 契约

`gmeta report`（以及 `gmeta run` 的 stdout）输出 **MetaReport**。字段稳定；
可能新增可选字段，同一大版本内既有字段不改变含义。

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

## 字段说明

| 字段 | 说明 |
| --- | --- |
| `method` | `kraken2_bracken` / `sylph_ani` / `centrifuge` / `kaiju` / `metaphlan` / `kmcp` |
| `qc.*` | 来源未提供的指标为 `null` |
| `taxa[].reads` | 估计/种级读段数；工具不报告时为 `0`（metaphlan rel_ab） |
| `taxa[].fraction` | 恒为 0..1 |
| `taxa[].ani` | 仅 sylph |
| `taxa[].confidence` | 丰度分档：high ≥10%、medium ≥1%、low <1%（sylph：ANI ≥95% / ≥90%） |
| `taxa[].priority` | 命中内置监测重点病原列表 |

## MethodEnvelope

`profile_*()` 函数返回 `{analysis_type, method, database, result}` 的
dataclass 信封（gside 家族契约）；`result` 承载方法相关细节
（`top_species`、计数），**不属于**稳定契约——需要稳定性请消费 MetaReport。
