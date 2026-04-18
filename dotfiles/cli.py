"""Typer command surface for the dotfiles tool.

This module is intentionally thin: each command resolves the active
configuration, builds a plan via :mod:`dotfiles.core`, surfaces warnings,
and only then executes. All the real work lives in ``core``, ``fs``, and
``vcs``; the CLI only translates arguments and prints results.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from . import __version__
from .config import Config, load_config, resolve_config_path
from .core import (
    TrackedStatus,
    execute_add,
    execute_eject,
    list_tracked,
    plan_add,
    plan_eject,
)
from .errors import DotfilesError

app = typer.Typer(
    name="dotfiles",
    help="Curate which dotfiles are kept under git version control.",
    no_args_is_help=True,
    add_completion=False,
)


# ---------------------------------------------------------------------------
# Shared option types
# ---------------------------------------------------------------------------


ConfigOption = Annotated[
    Optional[Path],
    typer.Option(
        "--config",
        help="Path to config.toml. Overrides DOTFILES_CONFIG and XDG defaults.",
    ),
]
DryRunOption = Annotated[
    bool,
    typer.Option("--dry-run", help="Show what would change without touching disk."),
]


def _load(config: Path | None) -> Config:
    """Load the config or exit with a friendly error."""
    try:
        return load_config(config)
    except DotfilesError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc


def _bail(exc: DotfilesError) -> None:
    """Print a DotfilesError and raise a non-zero Typer exit."""
    typer.echo(f"error: {exc}", err=True)
    raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the installed package version."""
    typer.echo(__version__)


@app.command()
def init(
    repo: Annotated[
        Path,
        typer.Option("--repo", help="Path to the tracked git repo to create."),
    ],
    home: Annotated[
        Optional[Path],
        typer.Option("--home", help="Override the home directory."),
    ] = None,
    repo_subdir: Annotated[
        str,
        typer.Option("--repo-subdir", help="Subdir inside the repo that mirrors home."),
    ] = "home",
    config: ConfigOption = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite an existing config file."),
    ] = False,
) -> None:
    """Scaffold the tracked repo and write a starter config.toml."""
    repo = repo.expanduser().absolute()
    repo.mkdir(parents=True, exist_ok=True)
    (repo / repo_subdir).mkdir(parents=True, exist_ok=True)

    if not (repo / ".git").exists():
        subprocess.run(["git", "-C", str(repo), "init", "--quiet"], check=True)

    gitignore = repo / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*.bak-*\n")


    config_path = resolve_config_path(config)
    if config_path.exists() and not force:
        typer.echo(
            f"error: config already exists at {config_path}. Pass --force to overwrite.",
            err=True,
        )
        raise typer.Exit(code=1)

    home_line = f'home = "{home.expanduser().absolute()}"\n' if home else ""
    body = (
        f'repo_path = "{repo}"\n'
        f'repo_subdir = "{repo_subdir}"\n'
        f"{home_line}"
        "ignored_paths = []\n"
        "auto_stage = false\n"
        "detect_nested_vcs = true\n"
        "relative_symlinks = false\n"
    )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(body)
    typer.echo(f"Initialised tracked repo at {repo}")
    typer.echo(f"Wrote config to {config_path}")


@app.command()
def add(
    path: Annotated[Path, typer.Argument(help="Home-side file or directory to track.")],
    stage: Annotated[
        bool,
        typer.Option("--stage", help="Also run `git add` in the tracked repo."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Backup and overwrite an existing repo-side destination."
        ),
    ] = False,
    follow_symlinks: Annotated[
        bool,
        typer.Option(
            "--follow-symlinks",
            help="Allow the source to be a symlink outside the repo.",
        ),
    ] = False,
    allow_nested_vcs: Annotated[
        bool,
        typer.Option("--allow-nested-vcs", help="Bypass the nested-git safety check."),
    ] = False,
    dry_run: DryRunOption = False,
    config: ConfigOption = None,
) -> None:
    """Move a file into the tracked repo and leave a symlink behind."""
    cfg = _load(config)
    stage = stage or cfg.auto_stage
    try:
        plan = plan_add(
            path,
            cfg,
            stage=stage,
            force=force,
            follow_symlinks=follow_symlinks,
            allow_nested_vcs=allow_nested_vcs,
        )
    except DotfilesError as exc:
        _bail(exc)
        return

    for w in plan.warnings:
        typer.echo(f"note: {w}")

    if plan.already_tracked:
        typer.echo(f"{plan.source} is already tracked; nothing to do.")
        return

    typer.echo(
        f"{'would move' if dry_run else 'moving'}: {plan.source} -> {plan.destination}"
    )
    if plan.stage:
        typer.echo("will `git add` after moving." if dry_run else "staging in repo...")

    try:
        result = execute_add(plan, dry_run=dry_run)
    except DotfilesError as exc:
        _bail(exc)
        return

    if result.backed_up is not None:
        typer.echo(f"backed up previous destination to {result.backed_up}")
    if result.executed:
        typer.echo("done.")


@app.command()
def eject(
    path: Annotated[Path, typer.Argument(help="Home-side symlink to restore.")],
    dry_run: DryRunOption = False,
    config: ConfigOption = None,
) -> None:
    """Replace a tracked symlink with the real file. The repo is untouched."""
    cfg = _load(config)
    try:
        plan = plan_eject(path, cfg)
    except DotfilesError as exc:
        _bail(exc)
        return

    typer.echo(
        f"{'would restore' if dry_run else 'restoring'}: {plan.source} <- {plan.target}"
    )
    try:
        execute_eject(plan, dry_run=dry_run)
    except DotfilesError as exc:
        _bail(exc)
        return
    if not dry_run:
        typer.echo("done.")


@app.command("list")
def list_cmd(
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON instead of a table."),
    ] = False,
    config: ConfigOption = None,
) -> None:
    """List every tracked dotfile and its health status."""
    cfg = _load(config)
    entries = list(list_tracked(cfg))

    if as_json:
        payload = [
            {
                "home_path": str(e.home_path),
                "repo_path": str(e.repo_path),
                "status": e.status.value,
            }
            for e in entries
        ]
        typer.echo(json.dumps(payload, indent=2))
        return

    if not entries:
        typer.echo("(no tracked entries)")
        return

    width = max(len(str(e.home_path)) for e in entries)
    for e in entries:
        typer.echo(f"{str(e.home_path):<{width}}  {e.status.value}")


@app.command()
def status(config: ConfigOption = None) -> None:
    """Summarise tracked-entry health counts."""
    cfg = _load(config)
    counts = {s: 0 for s in TrackedStatus}
    for entry in list_tracked(cfg):
        counts[entry.status] += 1
    for s, n in counts.items():
        typer.echo(f"{s.value:<10} {n}")


@app.command("restore-all")
def restore_all(
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the interactive confirmation."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Back up any home-side file that blocks a restore."
        ),
    ] = False,
    dry_run: DryRunOption = False,
    config: ConfigOption = None,
) -> None:
    """Recreate every symlink in ``$HOME`` from the tracked repo.

    Intended for fresh machines or after clobbering ``$HOME``.
    """
    cfg = _load(config)
    entries = list(list_tracked(cfg))
    actionable = [e for e in entries if e.status is not TrackedStatus.OK]
    if not actionable:
        typer.echo("Everything is already in place.")
        return

    typer.echo("The following entries would be (re)linked:")
    for e in actionable:
        typer.echo(f"  {e.home_path}  [{e.status.value}]")

    if dry_run:
        return
    if not _confirm(yes, "Proceed?"):
        typer.echo("Aborted.")
        raise typer.Exit(code=1)

    from .fs import backup_path, make_symlink

    for e in actionable:
        if e.home_path.exists() or e.home_path.is_symlink():
            if e.home_path.is_symlink() and e.status is TrackedStatus.BROKEN:
                e.home_path.unlink()
            elif force:
                backup_path(e.home_path)
            else:
                typer.echo(f"skipping {e.home_path}: already exists (pass --force)")
                continue
        make_symlink(e.home_path, e.repo_path, relative=cfg.relative_symlinks)
        typer.echo(f"linked {e.home_path}")


@app.command("eject-all")
def eject_all(
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the interactive confirmation."),
    ] = False,
    dry_run: DryRunOption = False,
    config: ConfigOption = None,
) -> None:
    """Eject every tracked entry back to its original home-side location.

    The tracked repo is left untouched, so the operation is reversible
    (run ``restore-all`` again).
    """
    cfg = _load(config)
    entries = [e for e in list_tracked(cfg) if e.status is TrackedStatus.OK]
    if not entries:
        typer.echo("No tracked entries to eject.")
        return

    typer.echo("The following entries would be ejected:")
    for e in entries:
        typer.echo(f"  {e.home_path} <- {e.repo_path}")

    if dry_run:
        return
    if not _confirm(yes, "Proceed?"):
        typer.echo("Aborted.")
        raise typer.Exit(code=1)

    for e in entries:
        try:
            plan = plan_eject(e.home_path, cfg)
            execute_eject(plan)
            typer.echo(f"ejected {e.home_path}")
        except DotfilesError as exc:
            typer.echo(f"skipped {e.home_path}: {exc}", err=True)


@app.command()
def doctor(config: ConfigOption = None) -> None:
    """Report configuration problems and broken symlinks."""
    cfg = _load(config)
    problems = 0
    if not cfg.repo_path.exists():
        typer.echo(f"repo_path does not exist: {cfg.repo_path}", err=True)
        problems += 1
    if not cfg.tracked_root.exists():
        typer.echo(f"tracked_root missing: {cfg.tracked_root}", err=True)
        problems += 1
    for e in list_tracked(cfg):
        if e.status is TrackedStatus.BROKEN:
            typer.echo(f"broken link: {e.home_path} -> {e.repo_path}", err=True)
            problems += 1
        elif e.status is TrackedStatus.REPLACED:
            typer.echo(
                f"replaced by regular file: {e.home_path} (expected symlink to {e.repo_path})",
                err=True,
            )
            problems += 1
    if problems == 0:
        typer.echo("OK — no issues found.")
    else:
        typer.echo(f"{problems} issue(s) found.", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _confirm(yes: bool, prompt: str) -> bool:
    """Prompt the user for confirmation, honouring ``--yes`` and non-TTY stdin.

    Args:
        yes: When True, skip the prompt and return True.
        prompt: The message to display before ``[y/N]``.

    Returns:
        True when the user agreed (or ``yes`` was passed).
    """
    if yes:
        return True
    if not sys.stdin.isatty():
        typer.echo(
            "error: refusing to proceed without --yes on a non-interactive stdin.",
            err=True,
        )
        return False
    return typer.confirm(prompt, default=False)
