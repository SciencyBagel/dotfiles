"""Shared pytest fixtures for the dotfiles test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles.config import Config


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    """A fake ``$HOME`` directory under ``tmp_path``."""
    home = tmp_path / "home"
    home.mkdir()
    return home


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """A fake tracked repo directory under ``tmp_path`` (not initialised)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "home").mkdir()
    return repo


@pytest.fixture
def cfg(fake_home: Path, fake_repo: Path) -> Config:
    """A minimal :class:`Config` pointing at the fake home/repo."""
    return Config(
        repo_path=fake_repo,
        home=fake_home,
        repo_subdir="home",
        ignored_paths=[],
    )
