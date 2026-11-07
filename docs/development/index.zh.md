# 开发

```bash
git clone https://github.com/indexofire/gmeta && cd gmeta
pixi install                     # 默认环境：工具 + gmeta（可编辑安装）
pixi run -e dev test             # dev 环境：另含 pytest/ruff/pyright/mkdocs
pixi run -e dev check            # ruff lint + 格式检查
pixi run -e dev fix              # 自动修复
pixi run -e dev typecheck        # pyright
pixi run -e dev docs             # 文档实时预览 localhost:8000
pixi run -e dev docs-build       # 严格构建 → site/
```

风格遵循 gside/gspec/gmlst 家族：click CLI 工厂、ruff（E/F/I/UP/B/SIM，
行宽 100）、`report/` 用 pydantic 模型、`analysis/` 用 dataclass 信封。

测试套件结构见[测试](testing.zh.md)。
