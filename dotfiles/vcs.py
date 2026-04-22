"""Git integration: nested-repo detection, gitignore checks, and staging.

``find_enclosing_vcs`` walks upward from a path looking for a ``.git``
entry, stopping at a configured boundary so the walk is always bounded.
``is_ignored_by_vcs`` consults a repo's ``.gitignore`` rules without
mutating anything, so callers in the pure planning layer can ask whether
a path is safe to move regardless of an enclosing repo. ``git_add``
shells out to git for staging.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import NewType


RepoPath = NewType("RepoPath", Path)


def find_enclosing_vcs(path: Path, *, stop_at: Path) -> RepoPath | None:
    """Return the nearest ancestor of ``path`` that contains a ``.git`` entry.

    The walk stops as soon as it reaches ``stop_at`` (exclusive) or the
    filesystem root, so it cannot wander outside the user's scope.

    Args:
        path: A path whose ancestry will be walked.
        stop_at: Boundary path; the walk stops when it reaches this ancestor.

    Returns:
        The ancestor directory holding ``.git``, or ``None`` if no nested
        repo was found within the bounded walk.
    """
    current = path if path.is_dir() else path.parent
    stop_at = stop_at.absolute()
    current = current.absolute()
    while True:
        if current == stop_at:
            return None
        if (current / ".git").exists():
            return RepoPath(current)
        if current.parent == current:
            return None
        current = current.parent


def git_add(repo: RepoPath, file: Path) -> None:
    """Run ``git add -- <file>`` inside ``repo``.

    Args:
        repo: Path to the git working tree.
        file: Path to stage. May be absolute; git resolves it relative to ``repo``.

    Raises:
        subprocess.CalledProcessError: If git exits non-zero.
    """
    subprocess.run(
        ["git", "-C", str(repo), "add", "--", str(file)],
        check=True,
    )


def is_ignored_by_vcs(repo: RepoPath, path: Path) -> bool:
    """Return True iff ``path`` is matched by a gitignore rule in ``repo``.

    Delegates to ``git check-ignore -q``, which exits 0 when the path is
    ignored, 1 when it is not, and 128 on other errors (e.g. the repo is
    unusable or git is unavailable). Any non-zero exit is treated as
    "not ignored" so the caller's existing safety checks are preserved
    when we cannot get a definitive answer.

    Args:
        repo: Path to the git working tree to consult.
        path: Path inside ``repo`` to test.

    Returns:
        True iff git reports ``path`` as ignored by ``repo``.
    """
    result = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "-q", "--", str(path)],
        capture_output=True,
    )
    return result.returncode == 0
