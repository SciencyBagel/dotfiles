"""Tests for :mod:`dotfiles.paths`."""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles.config import Config
from dotfiles.errors import PathOutsideHomeError
from dotfiles.paths import ensure_under_home, home_to_repo, is_under, repo_to_home


def test_is_under_basic(tmp_path: Path) -> None:
    parent = tmp_path / "p"
    child = parent / "c"
    assert is_under(child, parent)
    assert is_under(parent, parent)
    assert not is_under(tmp_path, parent)


def test_home_to_repo_mapping(cfg: Config) -> None:
    src = cfg.home / ".zshrc"
    assert home_to_repo(src, cfg) == cfg.repo_path / "home" / ".zshrc"


def test_home_to_repo_nested(cfg: Config) -> None:
    src = cfg.home / ".config" / "nvim" / "init.lua"
    assert (
        home_to_repo(src, cfg)
        == cfg.repo_path / "home" / ".config" / "nvim" / "init.lua"
    )


def test_repo_to_home_is_inverse(cfg: Config) -> None:
    src = cfg.home / ".config" / "foo.conf"
    repo = home_to_repo(src, cfg)
    assert repo_to_home(repo, cfg) == src


def test_home_to_repo_outside_home(cfg: Config, tmp_path: Path) -> None:
    with pytest.raises(PathOutsideHomeError):
        home_to_repo(tmp_path / "elsewhere" / "x", cfg)


def test_ensure_under_home_rejects_outside(cfg: Config, tmp_path: Path) -> None:
    with pytest.raises(PathOutsideHomeError):
        ensure_under_home(tmp_path / "elsewhere", cfg)
