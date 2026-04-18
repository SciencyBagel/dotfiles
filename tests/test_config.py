"""Tests for :mod:`dotfiles.config`."""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles.config import Config, load_config, resolve_config_path
from dotfiles.errors import ConfigError


def test_load_config_roundtrip(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        f'repo_path = "{repo}"\n'
        f'home = "{home}"\n'
        'repo_subdir = "home"\n'
        "ignored_paths = []\n"
    )
    cfg = load_config(cfg_path)
    assert cfg.repo_path == repo
    assert cfg.home == home
    assert cfg.repo_subdir == "home"
    assert cfg.tracked_root == repo / "home"


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.toml")


def test_load_config_malformed(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text("this is = = not toml")
    with pytest.raises(ConfigError):
        load_config(p)


def test_load_config_unknown_fields_rejected(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text(f'repo_path = "{tmp_path}"\nmystery_field = 1\n')
    with pytest.raises(ConfigError):
        load_config(p)


def test_config_rejects_repo_inside_home(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    repo = home / "repo"
    with pytest.raises(ValueError):
        Config(repo_path=repo, home=home)


def test_config_rejects_bad_subdir(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        Config(repo_path=tmp_path / "r", home=tmp_path / "h", repo_subdir="../escape")


def test_resolve_config_path_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "from-env.toml"
    monkeypatch.setenv("DOTFILES_CONFIG", str(cfg))
    assert resolve_config_path(None) == cfg


def test_resolve_config_path_explicit_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOTFILES_CONFIG", str(tmp_path / "env.toml"))
    explicit = tmp_path / "explicit.toml"
    assert resolve_config_path(explicit) == explicit
