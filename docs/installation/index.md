# Installation

gmeta is a Python 3.12 package driving external bioinformatics tools. Two
installation paths cover every scenario:

=== "pixi (recommended)"

    The repo ships a `pixi.toml` that pins every external tool — kraken2,
    bracken, sylph, fastp, minimap2, bowtie2, samtools — plus the Python
    package itself:

    ```bash
    git clone https://github.com/indexofire/gmeta
    cd gmeta
    pixi install          # default env: tools + gmeta
    pixi run -e dev test  # dev env: + pytest/ruff/pyright/mkdocs
    ```

=== "pip"

    The parser/report layer is pure Python; only `gmeta run` and coverage
    computation shell out to external binaries:

    ```bash
    pip install gmeta     # needs click/pydantic/jinja2/openpyxl/weasyprint
    ```

    Tools are resolved from `PATH` (or `GMETA_PIXI_BIN`); PDF output additionally
    requires a system `pango`.

## What lands where

| Path | Contents |
| --- | --- |
| `src/gmeta/data/` | Chinese name tables, priority pathogen list |
| `src/gmeta/templates/` | Jinja2 report template (HTML and PDF share it) |
| `$GMETA_DB_DIR` | databases (repo: `<repo>/data/db`; installed: `~/.local/share/gmeta/db`) |

## Next steps

- [Quick start](quick-start.md) — first sample end to end
- [Databases](databases.md) — kraken2/bracken/sylph/reference setup
