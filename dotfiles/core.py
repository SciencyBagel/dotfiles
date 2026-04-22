"""Planning and orchestration of add / eject / list operations.

The module is split along a pure/impure boundary:

* ``plan_*`` functions are pure: they inspect the filesystem read-only and
  return a frozen dataclass describing exactly what would change.
* ``execute_*`` functions are the only places that mutate state. They
  accept a plan and call into :mod:`dotfiles.fs` and :mod:`dotfiles.vcs`.

The CLI always calls ``plan_*`` first, surfaces warnings, and only then
passes the plan to ``execute_*``. This makes ``--dry-run`` trivial and
makes the planning logic easy to unit-test without any mocking.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator

from .config import Config
from .errors import (
    IgnoredPathError,
    MissingRepoFileError,
    NestedVCSError,
    NotASymlinkError,
    NotStagedError,
    SourceContainsRepoError,
    SourceNotFoundError,
    SymlinkOutsideRepoError,
    TargetExistsError,
)
from .fs import (
    backup_path,
    copy_path,
    ensure_parent,
    make_symlink,
    remove_path,
    restore_from_symlink,
)
from .paths import ensure_under_home, home_to_repo, is_under, repo_to_home
from .vcs import find_enclosing_vcs, git_add, is_ignored_by_vcs, RepoPath


# ---------------------------------------------------------------------------
# Pure predicates
# ---------------------------------------------------------------------------


def is_symlink_into_repo(p: Path, cfg: Config) -> bool:
    """Return True iff ``p`` is a symlink pointing into the tracked repo.

    Useful when trying to see if a file is already symlinked into the repo
    containing the version controlled dotfiles.

    """

    if not p.is_symlink():
        return False

    target = p.readlink()

    if not target.is_absolute():
        target = (p.parent / target).absolute()

    return is_under(target, cfg.tracked_root)


def is_ignored_by_config(p: Path, cfg: Config) -> bool:
    """Return True iff ``p`` is under any configured ``ignored_paths`` entry."""
    return any(is_under(p, ignored) for ignored in cfg.ignored_paths)


# ---------------------------------------------------------------------------
# Plan dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AddPlan:
    """The set of mutations ``dotfiles add`` would perform.

    Attributes:
        source: Home-side path that will be copied into the repo.
        destination: Repo-side path the file will be copied to.
        stage: Whether to ``git add`` ``destination`` after the copy.
        force: Whether an existing ``destination`` will be backed up instead of
            aborting.
        relative_symlinks: Carried forward for use by ``move`` later.
        already_tracked: When True, the source is already a symlink into the
            repo; ``execute_add`` is a no-op.
        already_staged: When True, the source has already been copied to the
            repo but the symlink has not been created yet; ``execute_add`` is a
            no-op and the user should run ``dotfiles move`` instead.
        warnings: Non-fatal notes to surface to the user.
    """

    source: Path
    destination: Path
    stage: bool = False
    force: bool = False
    relative_symlinks: bool = False
    already_tracked: bool = False
    already_staged: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MovePlan:
    """The mutations ``dotfiles move`` would perform.

    Attributes:
        source: Home-side path to replace with a symlink.
        destination: Repo-side path where the file was staged.
        relative_symlinks: Whether the symlink text should be relative to the
            home-side path's parent directory.
        already_linked: When True, ``source`` is already a symlink into the
            repo; ``execute_move`` is a no-op.
        warnings: Non-fatal notes to surface to the user.
    """

    source: Path
    destination: Path
    relative_symlinks: bool = False
    already_linked: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EjectPlan:
    """The mutations ``dotfiles eject`` would perform.

    Attributes:
        source: Home-side symlink to replace with the real file.
        target: Repo-side file the symlink currently points to.
    """

    source: Path
    target: Path


@dataclass
class AddResult:
    """Outcome of :func:`execute_add`."""

    plan: AddPlan
    executed: bool
    backed_up: Path | None = None


@dataclass
class EjectResult:
    """Outcome of :func:`execute_eject`."""

    plan: EjectPlan
    executed: bool


@dataclass
class MoveResult:
    """Outcome of :func:`execute_move`."""

    plan: MovePlan
    executed: bool


class TrackedStatus(str, Enum):
    """Health of a tracked entry as reported by :func:`list_tracked`."""

    OK = "ok"
    BROKEN = "broken"
    REPLACED = "replaced"
    MISSING = "missing"


@dataclass(frozen=True)
class TrackedEntry:
    """A single tracked dotfile.

    Attributes:
        home_path: Where the symlink should live in ``$HOME``.
        repo_path: The real file's path inside the tracked repo.
        status: Health of the entry.
    """

    home_path: Path
    repo_path: Path
    status: TrackedStatus


# ---------------------------------------------------------------------------
# Planners
# ---------------------------------------------------------------------------


def plan_add(
    src_path: Path,
    cfg: Config,
    *,
    stage: bool = False,
    force: bool = False,
    follow_symlinks: bool = False,
    allow_nested_vcs: bool = False,
) -> AddPlan:
    """Plan the addition of ``src`` to the tracked repo.

    Args:
        src: Path under ``cfg.home`` to track.
        cfg: Active configuration.
        stage: When True, ``execute_add`` will ``git add`` the moved file.
        force: When True, an existing repo-side destination is backed up
            rather than aborting.
        follow_symlinks: When True, a symlinked source that points outside
            the repo is still accepted (the link is replaced).
        allow_nested_vcs: When True, bypass the nested-VCS safety check.

    Returns:
        A frozen :class:`AddPlan` describing the intended mutations.

    Raises:
        SourceNotFoundError: If ``src`` does not exist.
        SourceContainsRepoError: If ``src`` is the tracked repo itself or
            contains it (moving ``src`` would move the repo into itself).
        IgnoredPathError: If ``src`` is under ``cfg.ignored_paths``.
        NestedVCSError: If ``src`` lies inside a nested ``.git`` that is
            actively tracking it, and ``allow_nested_vcs`` is False. Paths
            matched by the nested repo's ``.gitignore`` are allowed through
            (with a warning) since they cannot cause version-control
            conflicts.
        TargetExistsError: If the destination already exists and ``force`` is
            False.
        ValueError: If ``src`` is a symlink outside the repo and
            ``follow_symlinks`` is False.
    """
    src_path = ensure_under_home(src_path, cfg)
    warnings: list[str] = []

    if is_symlink_into_repo(src_path, cfg):
        dest = home_to_repo(src_path, cfg)
        return AddPlan(
            source=src_path,
            destination=dest,
            stage=stage,
            force=force,
            relative_symlinks=cfg.relative_symlinks,
            already_tracked=True,
            warnings=(f"{src_path} is already tracked.",),
        )

    if not src_path.exists() and not src_path.is_symlink():
        raise SourceNotFoundError(f"{src_path} does not exist.")

    if is_under(cfg.repo_path, src_path):
        raise SourceContainsRepoError(
            f"{src_path} equals or contains the tracked repo at {cfg.repo_path}; "
            "moving it would relocate the repo into itself."
        )

    if is_ignored_by_config(src_path, cfg):
        raise IgnoredPathError(f"{src_path} is under a configured ignored path.")

    if cfg.detect_nested_vcs and not allow_nested_vcs:
        src_nested_vcs_path = find_enclosing_vcs(src_path, stop_at=cfg.home)
        if src_nested_vcs_path is not None and src_nested_vcs_path != cfg.home:
            if is_ignored_by_vcs(src_nested_vcs_path, src_path):
                warnings.append(
                    f"{src_path} is inside a nested git repo at {src_nested_vcs_path}, "
                    "but is gitignored there — proceeding."
                )
            else:
                raise NestedVCSError(src_path, src_nested_vcs_path)

    if src_path.is_symlink() and not follow_symlinks:
        raise ValueError(
            f"{src_path} is a symlink that does not point into the tracked repo. "
            "Pass --follow-symlinks to move the symlink itself."
        )

    destination = home_to_repo(src_path, cfg)
    if destination.exists() or destination.is_symlink():
        if not src_path.is_symlink() and src_path.exists() and not force:
            # Home still has the original and the repo already has a copy —
            # the file was staged but not yet linked.  Signal this so the CLI
            # can hint the user to run ``dotfiles move``.
            return AddPlan(
                source=src_path,
                destination=destination,
                stage=stage,
                force=force,
                relative_symlinks=cfg.relative_symlinks,
                already_staged=True,
                warnings=(
                    f"{src_path} is already staged at {destination}. "
                    "Run `dotfiles move` to create the symlink.",
                ),
            )
        if not force:
            raise TargetExistsError(
                f"{destination} already exists in the repo. Pass --force to overwrite."
            )
        warnings.append(
            f"{destination} already exists; it will be backed up before being replaced."
        )

    return AddPlan(
        source=src_path,
        destination=destination,
        stage=stage,
        force=force,
        relative_symlinks=cfg.relative_symlinks,
        warnings=tuple(warnings),
    )


def plan_eject(src: Path, cfg: Config) -> EjectPlan:
    """Plan the restoration of a tracked file back to its home-side location.

    Args:
        src: The home-side symlink to restore.
        cfg: Active configuration.

    Returns:
        A frozen :class:`EjectPlan`.

    Raises:
        SourceNotFoundError: If ``src`` does not exist as a symlink.
        NotASymlinkError: If ``src`` is a regular file or directory.
        SymlinkOutsideRepoError: If the link target is not inside the repo.
        MissingRepoFileError: If the repo-side file is missing.
    """
    src = ensure_under_home(src, cfg)
    if not src.is_symlink():
        if src.exists():
            raise NotASymlinkError(f"{src} is not a symlink; nothing to eject.")
        raise SourceNotFoundError(f"{src} does not exist.")

    target_str = os.readlink(src)
    target = Path(target_str)
    if not target.is_absolute():
        target = (src.parent / target).absolute()

    if not is_under(target, cfg.tracked_root):
        raise SymlinkOutsideRepoError(
            f"{src} -> {target} does not point into the tracked repo at {cfg.tracked_root}."
        )
    if not target.exists():
        raise MissingRepoFileError(
            f"Symlink target {target} does not exist in the repo."
        )
    return EjectPlan(source=src, target=target)


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


def execute_add(plan: AddPlan, *, dry_run: bool = False) -> AddResult:
    """Apply an :class:`AddPlan` to disk.

    Copies ``plan.source`` into the repo without touching the original.
    Run :func:`execute_move` afterwards to replace the original with a symlink.

    Args:
        plan: Plan produced by :func:`plan_add`.
        dry_run: When True, perform no mutations; the returned result has
            ``executed=False``.

    Returns:
        An :class:`AddResult` summarising the outcome.
    """
    if plan.already_tracked or plan.already_staged or dry_run:
        return AddResult(plan=plan, executed=False)

    backed_up: Path | None = None
    if (plan.destination.exists() or plan.destination.is_symlink()) and plan.force:
        backed_up = backup_path(plan.destination)

    ensure_parent(plan.destination)
    copy_path(plan.source, plan.destination)
    if plan.stage:
        repo_root = _find_repo_root(plan.destination)
        if repo_root is not None:
            git_add(repo_root, plan.destination)

    return AddResult(plan=plan, executed=True, backed_up=backed_up)


def execute_eject(plan: EjectPlan, *, dry_run: bool = False) -> EjectResult:
    """Apply an :class:`EjectPlan` to disk.

    Args:
        plan: Plan produced by :func:`plan_eject`.
        dry_run: When True, perform no mutations.

    Returns:
        An :class:`EjectResult` summarising the outcome.
    """
    if dry_run:
        return EjectResult(plan=plan, executed=False)
    restore_from_symlink(plan.source)
    return EjectResult(plan=plan, executed=True)


def plan_move(src: Path, cfg: Config) -> MovePlan:
    """Plan the linking of a staged file (replace home-side original with a symlink).

    This is the second step of a two-step workflow:
    1. ``dotfiles add`` copies the file into the repo.
    2. ``dotfiles move`` removes the home-side original and creates a symlink.

    Args:
        src: Home-side path to link. Must have been staged via ``dotfiles add``.
        cfg: Active configuration.

    Returns:
        A frozen :class:`MovePlan`.

    Raises:
        NotStagedError: If the repo-side copy does not exist (file not yet staged).
    """
    src = ensure_under_home(src, cfg)

    if is_symlink_into_repo(src, cfg):
        dest = home_to_repo(src, cfg)
        return MovePlan(
            source=src,
            destination=dest,
            relative_symlinks=cfg.relative_symlinks,
            already_linked=True,
            warnings=(f"{src} is already linked to the repo.",),
        )

    destination = home_to_repo(src, cfg)
    if not destination.exists():
        raise NotStagedError(
            f"{src} has not been staged yet. Run `dotfiles add {src}` first."
        )

    return MovePlan(
        source=src,
        destination=destination,
        relative_symlinks=cfg.relative_symlinks,
    )


def execute_move(plan: MovePlan, *, dry_run: bool = False) -> MoveResult:
    """Apply a :class:`MovePlan` to disk.

    Removes the home-side original and creates a symlink pointing at the
    repo-side copy that was placed there by :func:`execute_add`.

    Args:
        plan: Plan produced by :func:`plan_move`.
        dry_run: When True, perform no mutations.

    Returns:
        A :class:`MoveResult` summarising the outcome.
    """
    if plan.already_linked or dry_run:
        return MoveResult(plan=plan, executed=False)

    if plan.source.exists() or plan.source.is_symlink():
        remove_path(plan.source)
    make_symlink(plan.source, plan.destination, relative=plan.relative_symlinks)
    return MoveResult(plan=plan, executed=True)


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def list_tracked(cfg: Config) -> Iterator[TrackedEntry]:
    """Yield every tracked file recorded under ``cfg.tracked_root``.

    A tracked entry's status is determined by inspecting the corresponding
    ``home_path``:

    * ``ok`` — it is a symlink into the repo and the target exists.
    * ``broken`` — it is a symlink into the repo but the target is missing.
    * ``replaced`` — a regular file/dir sits there instead of the symlink.
    * ``missing`` — nothing at all exists at the home path.

    Args:
        cfg: Active configuration.

    Yields:
        :class:`TrackedEntry` values; never mutates the filesystem.
    """
    root = cfg.tracked_root
    if not root.exists():
        return

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        # Depth cap based on the number of separators added beyond ``root``.
        depth = Path(dirpath).relative_to(root).parts
        if len(depth) > cfg.max_depth:
            dirnames.clear()
            continue
        for name in filenames:
            repo_path = Path(dirpath) / name
            home_path = repo_to_home(repo_path, cfg)
            yield TrackedEntry(
                home_path=home_path,
                repo_path=repo_path,
                status=_entry_status(home_path, repo_path, cfg),
            )


def _entry_status(home_path: Path, repo_path: Path, _: Config) -> TrackedStatus:
    """Classify a home-side path against its expected repo-side target."""
    if home_path.is_symlink():
        target = Path(os.readlink(home_path))
        if not target.is_absolute():
            target = (home_path.parent / target).absolute()
        if target == repo_path.absolute() or target.resolve() == repo_path.resolve():
            return TrackedStatus.OK if repo_path.exists() else TrackedStatus.BROKEN
        return TrackedStatus.REPLACED
    if home_path.exists():
        return TrackedStatus.REPLACED
    return TrackedStatus.MISSING


def _find_repo_root(p: Path) -> RepoPath | None:
    """Walk upward from ``p`` looking for a directory that contains ``.git``."""
    current = p.parent
    while True:
        if (current / ".git").exists():
            return RepoPath(current)
        if current.parent == current:
            return None
        current = current.parent
