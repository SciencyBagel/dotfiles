"""Tests for ``plan_move`` and ``execute_move``."""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles.config import Config
from dotfiles.core import execute_add, execute_move, plan_add, plan_move
from dotfiles.errors import NotStagedError


def _write(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_move_creates_symlink(cfg: Config) -> None:
    src = _write(cfg.home / ".zshrc", "zsh!")
    execute_add(plan_add(src, cfg))

    plan = plan_move(src, cfg)
    result = execute_move(plan)

    assert result.executed
    assert src.is_symlink()
    assert src.read_text() == "zsh!"  # via the symlink
    assert plan.destination.read_text() == "zsh!"


def test_move_dry_run_does_not_mutate(cfg: Config) -> None:
    src = _write(cfg.home / ".zshrc", "zsh!")
    execute_add(plan_add(src, cfg))

    plan = plan_move(src, cfg)
    execute_move(plan, dry_run=True)

    assert src.is_file() and not src.is_symlink()


def test_move_raises_if_not_staged(cfg: Config) -> None:
    src = _write(cfg.home / ".zshrc")
    with pytest.raises(NotStagedError):
        plan_move(src, cfg)


def test_move_already_linked_is_noop(cfg: Config) -> None:
    src = _write(cfg.home / ".zshrc")
    execute_add(plan_add(src, cfg))
    execute_move(plan_move(src, cfg))

    plan2 = plan_move(src, cfg)
    assert plan2.already_linked
    result = execute_move(plan2)
    assert not result.executed


def test_move_directory(cfg: Config) -> None:
    d = cfg.home / ".config" / "nvim"
    d.mkdir(parents=True)
    (d / "init.lua").write_text("-- config")

    execute_add(plan_add(d, cfg))
    plan = plan_move(d, cfg)
    result = execute_move(plan)

    assert result.executed
    assert d.is_symlink()
    assert (d / "init.lua").read_text() == "-- config"
    assert plan.destination.is_dir()


def test_add_then_move_full_workflow(cfg: Config) -> None:
    """Full two-step workflow: add stages, move links."""
    src = _write(cfg.home / ".bashrc", "bash!")

    add_result = execute_add(plan_add(src, cfg))
    assert add_result.executed
    # After add: original still present, repo copy exists
    assert src.is_file() and not src.is_symlink()
    dest = cfg.tracked_root / ".bashrc"
    assert dest.read_text() == "bash!"

    move_result = execute_move(plan_move(src, cfg))
    assert move_result.executed
    # After move: original replaced with symlink
    assert src.is_symlink()
    assert src.read_text() == "bash!"
