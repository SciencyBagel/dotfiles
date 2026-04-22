"""Tests for :mod:`dotfiles.vcs`."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from dotfiles.vcs import find_enclosing_vcs, git_add, is_ignored_by_vcs


def test_find_enclosing_vcs_none(tmp_path: Path) -> None:
    assert find_enclosing_vcs(tmp_path / "a" / "b", stop_at=tmp_path) is None


def test_find_enclosing_vcs_bounded(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()  # outside stop_at
    inner = tmp_path / "home" / "f"
    inner.parent.mkdir()
    inner.write_text("x")
    # stop_at is the 'home' dir, so the outer .git must NOT be found.
    assert find_enclosing_vcs(inner, stop_at=tmp_path / "home") is None


def test_find_enclosing_vcs_nested(tmp_path: Path) -> None:
    nested = tmp_path / "home" / "omz"
    nested.mkdir(parents=True)
    (nested / ".git").mkdir()
    inner = nested / "scripts" / "x"
    inner.parent.mkdir()
    inner.write_text("x")
    assert find_enclosing_vcs(inner, stop_at=tmp_path / "home") == nested


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_is_ignored_by_vcs_reports_gitignore_match(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
    (repo / ".gitignore").write_text("ignored.txt\n")
    (repo / "ignored.txt").write_text("x")
    (repo / "tracked.txt").write_text("y")

    from dotfiles.vcs import RepoPath

    assert is_ignored_by_vcs(RepoPath(repo), repo / "ignored.txt") is True
    assert is_ignored_by_vcs(RepoPath(repo), repo / "tracked.txt") is False


def test_is_ignored_by_vcs_returns_false_for_bogus_repo(tmp_path: Path) -> None:
    # A plain directory with no real git metadata: check-ignore should exit
    # non-zero and the helper must treat that as "not ignored" to preserve
    # the caller's safety check.
    fake = tmp_path / "fake"
    fake.mkdir()
    (fake / ".git").mkdir()

    from dotfiles.vcs import RepoPath

    assert is_ignored_by_vcs(RepoPath(fake), fake / "anything") is False


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_git_add_stages_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "t@t.t"], check=True
    )
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    f = repo / "a.txt"
    f.write_text("hi")
    git_add(repo, f)
    out = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert out.stdout.strip() == "a.txt"
