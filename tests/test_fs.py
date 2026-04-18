"""Tests for :mod:`dotfiles.fs`."""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles.errors import SymlinkLoopError
from dotfiles.fs import backup_path, make_symlink, move_path, restore_from_symlink


def test_move_path_file(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_text("hi")
    dst = tmp_path / "sub" / "b.txt"
    move_path(src, dst)
    assert not src.exists()
    assert dst.read_text() == "hi"


def test_make_symlink_basic(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("x")
    link = tmp_path / "link"
    make_symlink(link, target)
    assert link.is_symlink()
    assert link.read_text() == "x"


def test_make_symlink_relative(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "target.txt"
    target.parent.mkdir()
    target.write_text("x")
    link = tmp_path / "link"
    make_symlink(link, target, relative=True)
    import os
    assert os.readlink(link) == "sub/target.txt"


def test_make_symlink_rejects_self_loop(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    child = parent / "child"
    child.write_text("x")
    # Asking for a link at parent that points to child would make
    # walking `parent/` recurse indefinitely.
    with pytest.raises(SymlinkLoopError):
        make_symlink(parent, child)


def test_backup_path_renames(tmp_path: Path) -> None:
    p = tmp_path / "f"
    p.write_text("old")
    moved = backup_path(p)
    assert moved.exists()
    assert not p.exists()
    assert moved.name.startswith("f.bak-")


def test_restore_from_symlink_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "repo" / "file"
    target.parent.mkdir()
    target.write_text("payload")
    link = tmp_path / "home" / "link"
    link.parent.mkdir()
    make_symlink(link, target)
    restore_from_symlink(link)
    assert link.is_file() and not link.is_symlink()
    assert link.read_text() == "payload"
    assert not target.exists()
