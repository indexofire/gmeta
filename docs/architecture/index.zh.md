# 架构

gmeta 分三层组织，与 gside/gspec/gmlst 工具家族保持一致：

```text
cli.py ────────────── click 命令：run / report / net / db
analysis/ ─────────── 分析软件 + 执行器 + 预处理
report/ ───────────── 数据模型、格式渲染、识别网导出
```

模块地图与数据流见[分层设计](layers.zh.md)，稳定输出结构见
[JSON 契约](../reference/json-contract.zh.md)。
