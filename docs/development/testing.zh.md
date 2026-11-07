# 测试

```bash
pixi run -e dev test             # 全部测试
pixi run -e dev cov              # 带覆盖率
pixi run -e dev pytest tests/unit -q
pixi run -e dev pytest tests/integration -q
```

## 结构

```text
tests/
├── conftest.py                 kreport/bracken/fastp fixture（真实布局）
├── unit/
│   ├── test_kraken2_parse.py   kreport 树形 + bracken 解析
│   ├── test_profilers.py       centrifuge/kaiju/metaphlan/kmcp 解析器 + 嗅探
│   ├── test_executors.py       假二进制下的执行器
│   ├── test_coverage_parse.py  manifest/参考/reads 辅助函数
│   ├── test_network*.py        识别网行、工作表、适配层、CLI
│   ├── test_report_*.py        MetaReport 组装 + 渲染
│   ├── test_dbfetch.py         下载脚本生成
│   └── test_cli*.py            命令面
└── integration/
    └── test_coverage_integration.py   真实 minimap2+samtools（不在 PATH 时自动跳过）
```

## 约定

- **fixture 内嵌真实布局** —— kreport fixture 保留 kraken2 的精确列序与缩进，
  解析器回归会立刻暴露。
- **外部工具用 shell 脚本伪造**并放到 `GMETA_PIXI_BIN`（`test_executors.py`）：
  密封环境下走真实的二进制定位与子进程链路。
- **集成测试自动跳过**（二进制缺失时），任何机器都能 `pixi run -e dev test`。
- 交叉验证测试锚定 kraken2 树形路径与表格适配路径在识别网输出上的等价性——
  任一路径改动后必须保持通过。
