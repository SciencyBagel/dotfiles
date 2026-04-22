"""Tests for ``list_tracked`` and its status classification."""

from __future__ import annotations

from pathlib import Path

from dotfiles.config import Config
from dotfiles.core import (
    TrackedStatus,
    execute_add,
    execute_move,
    list_tracked,
    plan_add,
    plan_move,
)


def _track(cfg: Config, rel: str, content: str = "x") -> Path:
    src = cfg.home / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(content)
    execute_add(plan_add(src, cfg))
    execute_move(plan_move(src, cfg))
    return src


def test_list_empty(cfg: Config) -> None:
    assert list(list_tracked(cfg)) == []


def test_list_ok(cfg: Config) -> None:
    _track(cfg, ".zshrc")
    entries = list(list_tracked(cfg))
    assert len(entries) == 1
    assert entries[0].status is TrackedStatus.OK


def test_list_broken_when_target_removed(cfg: Config) -> None:
    _track(cfg, ".zshrc")
    (cfg.tracked_root / ".zshrc").unlink()
    entries = list(list_tracked(cfg))
    assert entries == []  # walker starts from repo; nothing to list after delete


def test_list_missing_when_home_link_removed(cfg: Config) -> None:
    src = _track(cfg, ".zshrc")
    src.unlink()
    entries = list(list_tracked(cfg))
    assert len(entries) == 1
    assert entries[0].status is TrackedStatus.MISSING


def test_list_replaced_when_regular_file(cfg: Config) -> None:
    src = _track(cfg, ".zshrc")
    src.unlink()
    src.write_text("replaced")
    entries = list(list_tracked(cfg))
    assert entries[0].status is TrackedStatus.REPLACED
