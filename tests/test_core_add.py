"""Tests for ``plan_add`` and ``execute_add``."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from dotfiles.config import Config
from dotfiles.core import execute_add, plan_add
from dotfiles.errors import (
    IgnoredPathError,
    NestedVCSError,
    SourceContainsRepoError,
    SourceNotFoundError,
    TargetExistsError,
)


def _write(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_add_file_copies_to_repo(cfg: Config) -> None:
    src = _write(cfg.home / ".zshrc", "zsh!")
    plan = plan_add(src, cfg)
    result = execute_add(plan)
    assert result.executed
    # Original is still a regular file (not yet replaced with symlink)
    assert src.is_file() and not src.is_symlink()
    # Repo copy has the same content
    assert plan.destination.read_text() == "zsh!"


def test_add_already_staged_is_noop(cfg: Config) -> None:
    src = _write(cfg.home / ".zshrc")
    execute_add(plan_add(src, cfg))
    plan2 = plan_add(src, cfg)
    assert plan2.already_staged
    result = execute_add(plan2)
    assert not result.executed


def test_add_dry_run_does_not_mutate(cfg: Config) -> None:
    src = _write(cfg.home / ".zshrc", "zsh!")
    plan = plan_add(src, cfg)
    execute_add(plan, dry_run=True)
    assert src.is_file() and not src.is_symlink()
    assert not plan.destination.exists()


def test_add_directory_copies_to_repo(cfg: Config) -> None:
    d = cfg.home / ".config" / "nvim"
    d.mkdir(parents=True)
    (d / "init.lua").write_text("-- config")
    plan = plan_add(d, cfg)
    execute_add(plan)
    # Original directory is still present (not yet replaced with symlink)
    assert d.is_dir() and not d.is_symlink()
    assert (d / "init.lua").read_text() == "-- config"
    # Repo copy exists
    assert plan.destination.is_dir()
    assert (plan.destination / "init.lua").read_text() == "-- config"


def test_add_source_not_found(cfg: Config) -> None:
    with pytest.raises(SourceNotFoundError):
        plan_add(cfg.home / "missing", cfg)


def test_add_already_staged_when_repo_copy_exists(cfg: Config) -> None:
    # When home still has the original and the repo already has a copy,
    # plan_add signals ``already_staged`` instead of raising TargetExistsError.
    src = _write(cfg.home / ".zshrc")
    dest = cfg.tracked_root / ".zshrc"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("existing")
    plan = plan_add(src, cfg)
    assert plan.already_staged


def test_add_refuses_target_exists_for_non_original(cfg: Config) -> None:
    # If the home-side file is a symlink (pointing elsewhere) and the repo
    # already has a file, TargetExistsError is still raised without --force.
    dest = cfg.tracked_root / ".zshrc"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("existing")
    outside = cfg.home / "outside"
    outside.write_text("x")
    link = cfg.home / ".zshrc"
    link.symlink_to(outside)
    with pytest.raises(TargetExistsError):
        plan_add(link, cfg, follow_symlinks=True)


def test_add_force_backs_up_existing_target(cfg: Config) -> None:
    src = _write(cfg.home / ".zshrc", "new")
    dest = cfg.tracked_root / ".zshrc"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("old")
    plan = plan_add(src, cfg, force=True)
    result = execute_add(plan)
    assert result.backed_up is not None
    assert result.backed_up.read_text() == "old"
    assert dest.read_text() == "new"


def test_add_refuses_nested_vcs(cfg: Config) -> None:
    omz = cfg.home / ".oh-my-zsh"
    omz.mkdir()
    (omz / ".git").mkdir()
    src = omz / "zshrc"
    src.write_text("x")
    with pytest.raises(NestedVCSError):
        plan_add(src, cfg)


def test_add_allow_nested_vcs_bypass(cfg: Config) -> None:
    omz = cfg.home / ".oh-my-zsh"
    omz.mkdir()
    (omz / ".git").mkdir()
    src = omz / "zshrc"
    src.write_text("x")
    plan = plan_add(src, cfg, allow_nested_vcs=True)
    assert not plan.already_tracked


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_add_allows_gitignored_in_nested_vcs(cfg: Config) -> None:
    omz = cfg.home / ".oh-my-zsh"
    omz.mkdir()
    subprocess.run(["git", "-C", str(omz), "init", "--quiet"], check=True)
    (omz / ".gitignore").write_text("custom.zsh\n")
    src = omz / "custom.zsh"
    src.write_text("# user-local override")

    plan = plan_add(src, cfg)

    assert not plan.already_tracked
    assert plan.source == src
    assert any("gitignored" in w for w in plan.warnings)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_add_still_refuses_tracked_file_in_nested_vcs(cfg: Config) -> None:
    omz = cfg.home / ".oh-my-zsh"
    omz.mkdir()
    subprocess.run(["git", "-C", str(omz), "init", "--quiet"], check=True)
    (omz / ".gitignore").write_text("custom.zsh\n")
    src = omz / "zshrc"
    src.write_text("# tracked by omz")

    with pytest.raises(NestedVCSError):
        plan_add(src, cfg)


def test_add_refuses_source_containing_repo(tmp_path: Path) -> None:
    # repo lives under home (a common convention); adding an ancestor of
    # the repo would relocate the repo into itself.
    home = tmp_path / "home"
    home.mkdir()
    repo = home / ".dotfiles-repo"
    (repo / "home").mkdir(parents=True)
    cfg = Config(repo_path=repo, home=home, repo_subdir="home")

    subdir = home / "sub"
    subdir.mkdir()
    repo_inside = subdir / "repo"
    (repo_inside / "home").mkdir(parents=True)
    cfg_inside = Config(repo_path=repo_inside, home=home, repo_subdir="home")

    with pytest.raises(SourceContainsRepoError):
        plan_add(home, cfg)  # src == home, repo is inside home
    with pytest.raises(SourceContainsRepoError):
        plan_add(subdir, cfg_inside)  # src is an ancestor of the repo


def test_add_repo_under_home_allows_sibling_paths(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    repo = home / ".dotfiles-repo"
    (repo / "home").mkdir(parents=True)
    cfg = Config(repo_path=repo, home=home, repo_subdir="home")

    src = home / ".zshrc"
    src.write_text("zsh!")
    plan = plan_add(src, cfg)
    assert plan.destination == repo / "home" / ".zshrc"


def test_add_refuses_ignored_path(cfg: Config) -> None:
    omz = cfg.home / ".oh-my-zsh"
    omz.mkdir()
    new_cfg = cfg.model_copy(update={"ignored_paths": [omz]})
    src = omz / "zshrc"
    src.write_text("x")
    with pytest.raises(IgnoredPathError):
        plan_add(src, new_cfg)
