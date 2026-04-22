"""Tests for ``plan_eject`` and ``execute_eject``."""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles.config import Config
from dotfiles.core import execute_add, execute_eject, execute_move, plan_add, plan_eject, plan_move
from dotfiles.errors import (
    MissingRepoFileError,
    NotASymlinkError,
    SourceNotFoundError,
    SymlinkOutsideRepoError,
)


def _track(cfg: Config, rel: str, content: str = "payload") -> Path:
    src = cfg.home / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(content)
    execute_add(plan_add(src, cfg))
    execute_move(plan_move(src, cfg))
    return src


def test_eject_roundtrip(cfg: Config) -> None:
    src = _track(cfg, ".zshrc", "hello")
    dest = cfg.tracked_root / ".zshrc"
    assert src.is_symlink() and dest.exists()

    plan = plan_eject(src, cfg)
    execute_eject(plan)

    assert src.is_file() and not src.is_symlink()
    assert src.read_text() == "hello"
    assert (
        not dest.exists()
    )  # per decision, repo was left to user — but eject moved file back


def test_eject_dry_run_noop(cfg: Config) -> None:
    src = _track(cfg, ".zshrc")
    plan = plan_eject(src, cfg)
    execute_eject(plan, dry_run=True)
    assert src.is_symlink()


def test_eject_refuses_non_symlink(cfg: Config) -> None:
    regular = cfg.home / ".regular"
    regular.write_text("x")
    with pytest.raises(NotASymlinkError):
        plan_eject(regular, cfg)


def test_eject_missing_source(cfg: Config) -> None:
    with pytest.raises(SourceNotFoundError):
        plan_eject(cfg.home / "nope", cfg)


def test_eject_refuses_link_outside_repo(cfg: Config, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.write_text("x")
    link = cfg.home / ".link"
    link.symlink_to(outside)
    with pytest.raises(SymlinkOutsideRepoError):
        plan_eject(link, cfg)


def test_eject_missing_repo_target(cfg: Config) -> None:
    src = _track(cfg, ".zshrc")
    # Delete the repo-side file to simulate corruption.
    (cfg.tracked_root / ".zshrc").unlink()
    with pytest.raises(MissingRepoFileError):
        plan_eject(src, cfg)
