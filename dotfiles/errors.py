"""Typed exception hierarchy for the dotfiles tool.

All errors raised by the package derive from :class:`DotfilesError` so CLI
code can catch a single base type and render a friendly message.
"""

from __future__ import annotations

from pathlib import Path


class DotfilesError(Exception):
    """Base class for every error raised by the dotfiles package."""


class ConfigError(DotfilesError):
    """Raised when the configuration is missing, malformed, or invalid."""


class PathOutsideHomeError(DotfilesError):
    """Raised when a supplied path is not under the configured home directory."""


class SourceNotFoundError(DotfilesError):
    """Raised when the home-side path to add/eject does not exist."""


class AlreadyTrackedError(DotfilesError):
    """Raised (or used as a warning) when a path is already a symlink into the repo."""


class TargetExistsError(DotfilesError):
    """Raised when the corresponding repo-side path already exists and ``--force`` was not given."""


class SourceContainsRepoError(DotfilesError):
    """Raised when the source to add would contain or equal the tracked repo.

    Moving such a path would try to relocate the repo into itself and is
    never what the user wants. Common trigger: ``dotfiles add ~`` when
    ``repo_path`` lives at ``~/.dotfiles-repo``.
    """


class NestedVCSError(DotfilesError):
    """Raised when the source sits inside a nested git repository.

    Attributes:
        path: The offending path passed to ``add``.
        vcs_root: The nearest enclosing ``.git`` directory's parent.
    """

    def __init__(self, path: Path, vcs_root: Path) -> None:
        super().__init__(
            f"{path} is inside a nested git repo at {vcs_root}. "
            f"Add '{vcs_root}' to ignored_paths or pass --allow-nested-vcs to override."
        )
        self.path = path
        self.vcs_root = vcs_root


class IgnoredPathError(DotfilesError):
    """Raised when the source is under a path explicitly listed in ``ignored_paths``."""


class NotASymlinkError(DotfilesError):
    """Raised during eject when the home-side path is not a symlink."""


class SymlinkOutsideRepoError(DotfilesError):
    """Raised during eject when the symlink target is not inside the tracked repo."""


class MissingRepoFileError(DotfilesError):
    """Raised during eject when the symlink's target file is missing from the repo."""


class SymlinkLoopError(DotfilesError):
    """Raised when a symlink operation would create a self-referential loop."""


class DepthLimitExceededError(DotfilesError):
    """Raised when a directory walk exceeds the configured maximum depth."""


class NotStagedError(DotfilesError):
    """Raised when ``move`` is called on a file that has not been staged via ``add`` yet."""
