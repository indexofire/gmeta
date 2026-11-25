"""Database-root resolution: always outside the package/repo."""

from __future__ import annotations

from pathlib import Path

from gmeta.config import _default_db_dir, resolve_db_dir


def test_default_is_xdg_data_home(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pixi.toml").touch()  # a checkout must not change the answer
    assert _default_db_dir(package_root=repo / "src" / "gmeta", project_root=repo) == (
        tmp_path / "xdg" / "gmeta" / "db"
    )


def test_installed_package_default_is_home_share(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    site_packages = tmp_path / "site-packages"
    resolved = _default_db_dir(package_root=site_packages / "gmeta", project_root=site_packages)
    assert resolved == Path.home() / ".local" / "share" / "gmeta" / "db"


def test_env_var_wins(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GMETA_DB_DIR", str(tmp_path / "custom"))
    assert resolve_db_dir() == tmp_path / "custom"
