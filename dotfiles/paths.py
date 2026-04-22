"""Pure home <-> repo path mapping.

This module contains only pure functions: no filesystem access, no mutation.
Callers are expected to pass absolute paths (use ``Path.expanduser().absolute()``
before calling).
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .errors import PathOutsideHomeError


def is_under(child: Path, parent: Path) -> bool:
    """Return True iff ``child`` is equal to or nested under ``parent``.

    Args:
        child: Candidate descendant path.
        parent: Candidate ancestor path.

    Returns:
        True if ``child`` is ``parent`` itself or any of its subpaths.
    """
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def ensure_under_home(p: Path, cfg: Config) -> Path:
    """Return ``p`` as an absolute path, asserting it is under ``cfg.home``.

    Args:
        p: Path to validate.
        cfg: Active configuration.

    Returns:
        The absolute form of ``p``.

    Raises:
        PathOutsideHomeError: If ``p`` is not under ``cfg.home``.
    """
    absolute = p.expanduser().absolute()
    if not is_under(absolute, cfg.home):
        raise PathOutsideHomeError(
            f"{absolute} is not under the configured home {cfg.home}"
        )
    return absolute


def home_to_repo(home_path: Path, cfg: Config) -> Path:
    """Map a home-relative path to its corresponding repo-side path.

    Args:
        home_path: Absolute path inside ``cfg.home``.
        cfg: Active configuration.

    Returns:
        The corresponding path inside ``cfg.tracked_root``.

    Raises:
        PathOutsideHomeError: If ``home_path`` is not under ``cfg.home``.
    """
    if not is_under(home_path, cfg.home):
        raise PathOutsideHomeError(
            f"{home_path} is not under the configured home {cfg.home}"
        )
    rel = home_path.relative_to(cfg.home)
    return cfg.tracked_root / rel


def repo_to_home(repo_path: Path, cfg: Config) -> Path:
    """Map a repo-side path back to its corresponding home-side path.

    Args:
        repo_path: Absolute path inside ``cfg.tracked_root``.
        cfg: Active configuration.

    Returns:
        The corresponding path inside ``cfg.home``.

    Raises:
        ValueError: If ``repo_path`` is not under ``cfg.tracked_root``.
    """
    rel = repo_path.relative_to(cfg.tracked_root)
    return cfg.home / rel
