from dataclasses import dataclass
from pathlib import Path


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
