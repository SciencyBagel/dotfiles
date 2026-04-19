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

from pydantic import BaseModel, Field, field_validator

from .errors import ConfigError


def _expand(p: Path) -> Path:
    """Expand ``~`` and return an absolute path (no filesystem resolution)."""
    return Path(os.path.expanduser(str(p))).absolute()


class Config(BaseModel):
    """Runtime configuration for the dotfiles tool."""

    repo_path: Annotated[Path, Field(description="Git repo storing the real files.")]
    """Git repository where the real files are stored."""

    home: Annotated[Path, Field(default_factory=Path.home)]
    """Directory the tool treats as ``$HOME``. Defaults to :func:`Path.home`"""

    repo_subdir: Annotated[str, Field(default="home")]
    """Subdirectory inside ``repo_path`` where the home-relative tree is mirrored. Defaults to ``"home"``."""

    ignored_paths: Annotated[list[Path], Field(default_factory=list)]
    """Paths inside ``home`` that must never be touched
            (existing submodule-style repos like oh-my-zsh or LazyVim)."""

    allowed_paths: Annotated[list[Path], Field(default_factory=list)]
    """Declarative hole-punch through ``ignored_paths`` and the nested-VCS
            check. Any source under an ``allowed_paths`` entry is exempt from
            both for that ``add`` call. Intended for user-extension points
            inside third-party repos (e.g. ``~/.oh-my-zsh/custom``)."""

    auto_stage: Annotated[bool, Field(default=False)]
    """Default value of the ``--stage`` flag on ``add``."""

    detect_nested_vcs: Annotated[bool, Field(default=True)]
    """When ``True``, refuse to add files that sit inside
            a nested git repository."""

    trust_nested_gitignore: Annotated[bool, Field(default=True)]
    """When ``True``, if a nested repo is detected and its own ``.gitignore``
            already ignores the source, allow the ``add`` anyway. Zero-config
            handling of user overrides in repos that expect them (e.g.
            oh-my-zsh's ``custom/``)."""

    relative_symlinks: Annotated[bool, Field(default=False)]
    """When ``True``, create relative symlinks; otherwise
            absolute (survives moves of the home directory but not of the repo)."""

    max_depth: Annotated[int, Field(default=64, gt=0)]
    """Safety cap on directory walks."""

    model_config = {"extra": "forbid"}

    @field_validator("repo_path", "home", mode="before")
    @classmethod
    def _expand_path(cls, v: object) -> object:
        """Expand ``~`` on incoming path strings before pydantic type coerces."""
        if isinstance(v, (str, Path)):
            return _expand(Path(v))
        return v

    @field_validator("ignored_paths", "allowed_paths", mode="before")
    @classmethod
    def _expand_path_list(cls, v: object) -> object:
        """Expand each entry in ``ignored_paths`` / ``allowed_paths``."""
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
