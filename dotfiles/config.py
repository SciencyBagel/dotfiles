"""Configuration model and TOML loader.

The :class:`Config` pydantic model captures every tunable knob of the
dotfiles tool. ``load_config`` is a pure function that reads a TOML file
and returns a validated :class:`Config`; the CLI calls it exactly once and
threads the result through every command.

Discovery precedence (highest to lowest):
    1. Explicit path passed to :func:`load_config` (from ``--config`` flag).
    2. ``DOTFILES_CONFIG`` environment variable.
    3. ``$XDG_CONFIG_HOME/dotfiles/config.toml``.
    4. ``~/.config/dotfiles/config.toml``.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from .errors import ConfigError


def _expand(p: Path) -> Path:
    """Expand ``~`` and return an absolute path (no filesystem resolution)."""
    return Path(os.path.expanduser(str(p))).absolute()


class Config(BaseModel):
    """Runtime configuration for the dotfiles tool.

    Attributes:
        repo_path: Git repository where the real files are stored.
        home: Directory the tool treats as ``$HOME``. Defaults to :func:`Path.home`.
        repo_subdir: Subdirectory inside ``repo_path`` where the home-relative
            tree is mirrored. Defaults to ``"home"``.
        ignored_paths: Paths inside ``home`` that must never be touched
            (existing submodule-style repos like oh-my-zsh or LazyVim).
        auto_stage: Default value of the ``--stage`` flag on ``add``.
        detect_nested_vcs: When ``True``, refuse to add files that sit inside
            a nested git repository.
        relative_symlinks: When ``True``, create relative symlinks; otherwise
            absolute (survives moves of the home directory but not of the repo).
        max_depth: Safety cap on directory walks.
    """

    repo_path: Annotated[Path, Field(description="Git repo storing the real files.")]
    home: Annotated[Path, Field(default_factory=Path.home)]
    repo_subdir: Annotated[str, Field(default="home")]
    ignored_paths: Annotated[list[Path], Field(default_factory=list)]
    auto_stage: Annotated[bool, Field(default=False)]
    detect_nested_vcs: Annotated[bool, Field(default=True)]
    relative_symlinks: Annotated[bool, Field(default=False)]
    max_depth: Annotated[int, Field(default=64, gt=0)]

    model_config = {"extra": "forbid"}

    @field_validator("repo_path", "home", mode="before")
    @classmethod
    def _expand_path(cls, v: object) -> object:
        """Expand ``~`` on incoming path strings before pydantic type coerces."""
        if isinstance(v, (str, Path)):
            return _expand(Path(v))
        return v

    @field_validator("ignored_paths", mode="before")
    @classmethod
    def _expand_ignored(cls, v: object) -> object:
        """Expand each entry in ``ignored_paths``."""
        if isinstance(v, list):
            return [_expand(Path(p)) if isinstance(p, (str, Path)) else p for p in v]
        return v

    @field_validator("repo_subdir")
    @classmethod
    def _no_slashes_subdir(cls, v: str) -> str:
        """Disallow path separators in ``repo_subdir`` to keep the mapping trivial."""
        if v and (v.startswith("/") or ".." in Path(v).parts):
            raise ValueError("repo_subdir must be a plain directory name, not a path")
        return v

    @model_validator(mode="after")
    def _validate_no_self_containment(self) -> "Config":
        """Reject configs where ``repo_path`` sits inside ``home``.

        A repo under ``home`` would be tracked by itself the moment the user
        tries to add anything in that region, producing symlink cycles.
        """
        # FIXME: it's better to check when the user tries to add the
        # ``repo_path`` under home instead.
        try:
            self.repo_path.relative_to(self.home)
        except ValueError:
            return self
        raise ValueError(
            f"repo_path {self.repo_path} must not be inside home {self.home}"
        )

    @property
    def tracked_root(self) -> Path:
        """Return the directory inside the repo that mirrors ``home``."""
        return self.repo_path / self.repo_subdir if self.repo_subdir else self.repo_path


def _default_config_path() -> Path:
    """Return the default config path following the XDG convention."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "dotfiles" / "config.toml"


def resolve_config_path(explicit: Path | None = None) -> Path:
    """Resolve which config path to load based on the precedence rules.

    Args:
        explicit: Path passed via ``--config``, if any.

    Returns:
        The path the tool should attempt to load.
    """
    if explicit is not None:
        return _expand(explicit)

    env = os.environ.get("DOTFILES_CONFIG")
    if env:
        return _expand(Path(env))

    return _default_config_path()


def load_config(path: Path | None = None) -> Config:
    """Load and validate a :class:`Config` from a TOML file.

    Args:
        path: Explicit config path. When ``None``, discovery rules apply.

    Returns:
        A validated :class:`Config` instance.

    Raises:
        ConfigError: If the file is missing, cannot be parsed, or fails validation.
    """
    resolved = resolve_config_path(path)
    if not resolved.exists():
        raise ConfigError(
            f"Config file not found at {resolved}. Run `dotfiles init` to create one."
        )

    try:
        with resolved.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Failed to parse TOML at {resolved}: {exc}") from exc

    try:
        return Config.model_validate(data)
    except Exception as exc:  # pydantic ValidationError is a subclass of ValueError
        raise ConfigError(f"Invalid config at {resolved}: {exc}") from exc
