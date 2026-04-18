"""dotfiles: a small CLI for curating which files in ``$HOME`` live under git.

Overview
--------
The tool replaces a real file in ``$HOME`` with a symlink and moves the
original into a dedicated git repository. The repo mirrors the home tree
under a configurable subdirectory (``home/`` by default), so
``~/.config/nvim/init.lua`` becomes ``<repo>/home/.config/nvim/init.lua``.

Module layout
-------------
``cli``       Typer command surface. Thin layer — every command calls
              into :mod:`dotfiles.core`.
``config``    Pydantic :class:`Config` model and TOML loader.
``paths``    Pure home<->repo path mapping utilities.
``core``     Pure planners (``plan_add``, ``plan_eject``, ``list_tracked``)
              plus orchestrators (``execute_add``, ``execute_eject``). The
              planner/executor split makes ``--dry-run`` trivial.
``fs``       Side-effecting filesystem primitives (the only place mutations
              happen). Owns symlink-loop guards.
``vcs``      Git integration: nested-repo detection and ``git add`` staging.
``errors``   Typed exception hierarchy.

See ``ARCHITECTURE.md`` at the repo root for cross-cutting design rationale
(safety nets, loop-and-cycle guarantees, testing philosophy).
"""

__version__ = "0.1.0"
