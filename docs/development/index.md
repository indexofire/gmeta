# Development

```bash
git clone https://github.com/indexofire/gmeta && cd gmeta
pixi install                     # default env: tools + gmeta (editable)
pixi run -e dev test             # dev env: + pytest/ruff/pyright/mkdocs
pixi run -e dev check            # ruff lint + format check
pixi run -e dev fix              # auto-fix
pixi run -e dev typecheck        # pyright
pixi run -e dev docs             # live docs at localhost:8000
pixi run -e dev docs-build       # strict build → site/
```

Style follows the gside/gspec/gmlst family: click CLI factories, ruff
(E/F/I/UP/B/SIM, line length 100), pydantic models in `report/`, dataclass
envelopes in `analysis/`.

See [Testing](testing.md) for the suite layout and conventions.
