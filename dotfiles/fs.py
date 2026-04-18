"""Side-effecting filesystem primitives.

This is the only module in the package that mutates the filesystem. Each
function is deliberately small and individually mockable; ``core.execute_*``
composes them to perform the user's intent.

The loop-safety guarantees for symlink creation live here:
:func:`make_symlink` refuses to produce a link that points at itself or at
any of its own ancestors.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from .errors import SymlinkLoopError


def ensure_parent(p: Path) -> None:
    """Create parent directories of ``p`` if they don't already exist."""
    p.parent.mkdir(parents=True, exist_ok=True)


def move_path(src: Path, dst: Path) -> None:
    """Move a file or directory from ``src`` to ``dst``.

    Parent directories of ``dst`` are created as needed. ``shutil.move`` is
    used so same-filesystem renames stay atomic while cross-device moves
    fall back to copy + delete.

    Args:
        src: Path to move.
        dst: Destination path. Must not already exist.
    """
    ensure_parent(dst)
    shutil.move(str(src), str(dst))


def _would_loop(link: Path, target: Path) -> bool:
    """Return True if symlinking ``link`` -> ``target`` would create a loop.

    A loop is possible when the link path equals the target, or when the
    target lives inside the link's own subtree. Walking into the link would
    then revisit ``link`` indefinitely.
    """
    link = link.absolute()
    target = target.absolute()
    if link == target:
        return True
    try:
        target.relative_to(link)
    except ValueError:
        return False
    return True


def make_symlink(link: Path, target: Path, *, relative: bool = False) -> None:
    """Create a symlink at ``link`` pointing to ``target``.

    Args:
        link: Path where the symlink should be created. Must not already exist.
        target: Path the symlink will resolve to. Must already exist on disk.
        relative: When True, the stored link text is ``target`` relative to
            ``link.parent``; otherwise the absolute target is stored.

    Raises:
        SymlinkLoopError: If the proposed link would point at itself or at
            one of its own ancestors.
        FileExistsError: If ``link`` already exists.
        FileNotFoundError: If ``target`` does not exist.
    """
    if _would_loop(link, target):
        raise SymlinkLoopError(
            f"Refusing to create symlink {link} -> {target}: would create a cycle."
        )
    if not target.exists():
        raise FileNotFoundError(f"Symlink target does not exist: {target}")
    ensure_parent(link)
    link_text: str | os.PathLike[str]
    if relative:
        link_text = os.path.relpath(target, start=link.parent)
    else:
        link_text = str(target.absolute())
    os.symlink(link_text, link)


def backup_path(p: Path) -> Path:
    """Rename ``p`` to ``p.bak-<timestamp>`` and return the new path.

    Args:
        p: Existing path to move aside.

    Returns:
        The new path of the moved-aside file.
    """
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = p.with_name(f"{p.name}.bak-{stamp}")
    i = 0
    while candidate.exists():
        i += 1
        candidate = p.with_name(f"{p.name}.bak-{stamp}-{i}")
    p.rename(candidate)
    return candidate


def restore_from_symlink(link: Path) -> Path:
    """Replace a symlink with the real file it points to.

    Reads ``link`` with :func:`os.readlink` exactly once (no resolution of
    chained symlinks), then moves the target file back to ``link``.

    Args:
        link: A symlink on disk.

    Returns:
        The resolved target path that was moved back.

    Raises:
        FileNotFoundError: If the symlink's target does not exist.
    """
    target_str = os.readlink(link)
    target = Path(target_str)
    if not target.is_absolute():
        target = (link.parent / target).absolute()
    if not target.exists():
        raise FileNotFoundError(
            f"Symlink {link} points to {target}, which does not exist."
        )
    link.unlink()
    shutil.move(str(target), str(link))
    return target
