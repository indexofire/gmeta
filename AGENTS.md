# AGENTS.md — gmeta 项目约定

## 发布策略（重要）

**版本号变更与新版本发布，仅在用户明确说"发布新版本"时执行。** 包括：

- 修改 `pyproject.toml` / `pixi.toml` 的 `version`
- 在 CHANGELOG 中把 `[Unreleased]` 固化为版本条目
- 打 git tag（`vX.Y.Z`）
- 创建 GitHub Release
- 上传 PyPI（`twine upload` / publish workflow）

普通修复、功能迭代、文档更新只做：代码修改 → 测试/lint → commit → push。
CHANGELOG 的新条目留在 `[Unreleased]` 段落，等发布指令时再固化。

## 提交习惯

- commit message 用英文前缀（`fix(...)` / `feat(...)` / `docs(...)` / `ci(...)` / `release: gmeta X.Y.Z`），正文可中文。
- 推送目标：`origin main`（https://github.com/indexofire/gmeta.git）。

## 质量门禁（提交前）

```bash
./.pixi/envs/dev/bin/python -m pytest tests/ -q
./.pixi/envs/dev/bin/ruff check src/ tests/ && ./.pixi/envs/dev/bin/ruff format --check src/ tests/
./.pixi/envs/dev/bin/mkdocs build --strict
```

## pixi 版本约定

- 使用 **pixi ≥ 0.68**（v7 lock 格式；v6 会把源码 hash 写进 lock，导致源码改动频繁重写 lock）。
- 仓库的 `pixi.lock` 是 **version 7** 且必须提交；只有真实依赖变更（`pixi add/remove`）时才产生新的 lock diff。
- 若本机 pixi 较老把 lock 改回 v6：`pixi self-update` 后 `git checkout -- pixi.lock`，不要提交降级格式。
