# 使用

三个命令族共享同一套解析器与报告模型：

| 命令 | 输入 | 输出 |
| --- | --- | --- |
| [`gmeta run`](cli.zh.md#run) | FASTQ | 流程：质控 → 去宿主 → 物种分析 → 报告 |
| [`gmeta report`](cli.zh.md#report) | 分析结果文件 | JSON/HTML/Excel/PDF 报告 |
| [`gmeta net build`](network.zh.md) | 分析结果文件 | 识别网上报工作簿 |

## 方法矩阵

六个分析软件都同时支持**执行**（`gmeta run -m <method>`）和**导入**
（`gmeta report` / `gmeta net build`）：

| 方法 | 执行 | 导入格式 |
| --- | :---: | --- |
| kraken2 + bracken | ✅ | kreport、bracken 表 |
| sylph | ✅ | profile TSV |
| centrifuge | ✅ | 原生 report、kreport（经 centrifuge-kreport） |
| kaiju | ✅ | kaiju2table（种级 + 属级） |
| metaphlan | ✅ | profile（rel_ab / rel_ab_w_read_stats） |
| kmcp | ✅ | compute profile TSV（17 列） |

## 去哪里看

- [CLI 参考](cli.zh.md) —— run/report/db 的全部参数
- [识别网导出](network.zh.md) —— 上报工作簿详解
- [支持的分析软件](profilers.zh.md) —— 各工具输入格式与语义
- [覆盖度计算](coverage.zh.md) —— 种基因组覆盖度的计算方式
