"""Git integration: nested-repo detection and optional staging.

``find_enclosing_vcs`` walks upward from a path looking for a ``.git``
entry, stopping at a configured boundary so the walk is always bounded.
``git_add`` shells out to git for staging.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def find_enclosing_vcs(path: Path, *, stop_at: Path) -> Path | None:
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
            return current
        if current.parent == current:
            return None
        current = current.parent


def git_add(repo: Path, file: Path) -> None:
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
