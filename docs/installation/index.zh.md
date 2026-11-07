# 安装

gmeta 是一个驱动外部生信工具的 Python 3.12 包。两种安装方式覆盖所有场景：

=== "pixi（推荐）"

    仓库自带 `pixi.toml`，固定了全部外部工具——kraken2、bracken、sylph、fastp、
    minimap2、bowtie2、samtools——以及 Python 包本身：

    ```bash
    git clone https://github.com/indexofire/gmeta
    cd gmeta
    pixi install          # 默认环境：工具 + gmeta
    pixi run -e dev test  # dev 环境：另含 pytest/ruff/pyright/mkdocs
    ```

=== "pip"

    解析/报告层是纯 Python；只有 `gmeta run` 和覆盖度计算会调用外部程序：

    ```bash
    pip install gmeta     # 依赖 click/pydantic/jinja2/openpyxl/weasyprint
    ```

    工具从 `PATH`（或 `GMETA_PIXI_BIN`）解析；PDF 输出还需要系统 `pango`。

## 东西都装在哪

| 路径 | 内容 |
| --- | --- |
| `src/gmeta/data/` | 中文名映射表、重点病原列表 |
| `src/gmeta/templates/` | Jinja2 报告模板（HTML 与 PDF 共用） |
| `$GMETA_DB_DIR` | 数据库根目录（仓库检出：`<repo>/data/db`；pip 安装：`~/.local/share/gmeta/db`） |

## 下一步

- [快速开始](quick-start.zh.md) —— 端到端跑第一个样本
- [数据库](databases.zh.md) —— kraken2/bracken/sylph/参考基因组配置
