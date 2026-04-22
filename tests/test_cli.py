"""End-to-end tests for the Typer CLI."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dotfiles.cli import app

runner = CliRunner()


def _write_config(tmp_path: Path, home: Path, repo: Path) -> Path:
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'repo_path = "{repo}"\nhome = "{home}"\nrepo_subdir = "home"\n')
    return cfg


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_add_list_eject_roundtrip(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    repo = tmp_path / "repo"
    (repo / "home").mkdir(parents=True)
    cfg = _write_config(tmp_path, home, repo)

    target = home / ".zshrc"
    target.write_text("zsh!")

    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0

    res = runner.invoke(app, ["add", str(target), "--config", str(cfg)])
    assert res.exit_code == 0, res.stdout
    # After add: original still present (staged, not yet linked)
    assert target.is_file() and not target.is_symlink()

    res = runner.invoke(app, ["move", str(target), "--config", str(cfg)])
    assert res.exit_code == 0, res.stdout
    assert target.is_symlink()

    res = runner.invoke(app, ["list", "--config", str(cfg)])
    assert res.exit_code == 0
    assert ".zshrc" in res.stdout
    assert "ok" in res.stdout

    res = runner.invoke(app, ["eject", str(target), "--config", str(cfg)])
    assert res.exit_code == 0, res.stdout
    assert target.is_file() and not target.is_symlink()
    assert target.read_text() == "zsh!"


def test_add_dry_run_no_mutation(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    repo = tmp_path / "repo"
    (repo / "home").mkdir(parents=True)
    cfg = _write_config(tmp_path, home, repo)
    target = home / ".zshrc"
    target.write_text("zsh!")

    res = runner.invoke(app, ["add", str(target), "--dry-run", "--config", str(cfg)])
    assert res.exit_code == 0
    assert target.is_file() and not target.is_symlink()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_add_with_stage_hits_git_index(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "home").mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "t@t.t"], check=True
    )
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)

    cfg = _write_config(tmp_path, home, repo)
    target = home / ".zshrc"
    target.write_text("zsh!")

    res = runner.invoke(app, ["add", str(target), "--stage", "--config", str(cfg)])
    assert res.exit_code == 0, res.stdout

    out = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "home/.zshrc" in out.stdout


def test_add_refuses_nested_vcs(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".oh-my-zsh").mkdir()
    (home / ".oh-my-zsh" / ".git").mkdir()
    (home / ".oh-my-zsh" / "zshrc").write_text("x")
    repo = tmp_path / "repo"
    (repo / "home").mkdir(parents=True)
    cfg = _write_config(tmp_path, home, repo)

    res = runner.invoke(
        app, ["add", str(home / ".oh-my-zsh" / "zshrc"), "--config", str(cfg)]
    )
    assert res.exit_code != 0
    assert "nested" in (res.stdout + res.stderr).lower()
