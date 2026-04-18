# Architecture

This document captures cross-cutting design decisions that would otherwise
be duplicated across docstrings. For per-function details, read the
Google-style docstrings in each module.

## Repo layout convention

The tracked repo mirrors `$HOME` under a single configurable subdirectory.
With the default `repo_subdir = "home"`:

```
~/.zshrc                              ->  <repo>/home/.zshrc
~/.config/nvim/init.lua               ->  <repo>/home/.config/nvim/init.lua
```

This leaves the repo's root free for its own `README.md`, CI, and scripts,
and keeps the mapping trivially reversible. The pure mapping lives in
[`dotfiles/paths.py`](./dotfiles/paths.py).

## Plan / execute split

Every mutating operation is split in two:

* `plan_<op>` in [`dotfiles/core.py`](./dotfiles/core.py) is **pure**. It
  inspects the filesystem read-only and returns a frozen `*Plan`
  dataclass describing every intended change.
* `execute_<op>` is the only code that mutates state. It accepts a plan
  and delegates to [`dotfiles/fs.py`](./dotfiles/fs.py) /
  [`dotfiles/vcs.py`](./dotfiles/vcs.py).

Benefits:

* `--dry-run` is a one-liner — we build the plan and skip the executor.
* The planner is trivially unit-testable with no mocks.
* Surfaces warnings *before* touching disk.

## Safety nets for destructive commands

1. **Build plan, then print it.** Every command prints what it would do
   before doing it.
2. **`--dry-run` available everywhere** that mutates state.
3. **Interactive confirmation for bulk ops.** `restore-all` and
   `eject-all` prompt `y/N` and refuse to proceed on a non-TTY stdin
   unless `--yes` is passed.
4. **Refuse-by-default for overwrites.** `add` aborts if the repo-side
   destination already exists. With `--force`, the existing file is
   backed up to `<path>.bak-<timestamp>` via `fs.backup_path` instead of
   being deleted.
5. **Nested-VCS detection is on by default.** `find_enclosing_vcs` walks
   upward from the source looking for `.git`. If one is found, `add`
   refuses with an actionable message pointing at the `ignored_paths`
   config entry.
6. **All operations assert paths stay under `cfg.home`.** See
   `paths.ensure_under_home`.
7. **Atomic per-entry execution** in bulk ops — a mid-batch failure does
   not leave the filesystem half-mutated across entries.

## Loop and cycle safety

Dotfiles configuration legitimately contains symlinks (oh-my-zsh,
LazyVim, XDG `~/.config` children). The tool must never infinite-loop
or blindly descend into unintended trees.

1. **`os.walk(..., followlinks=False)`** in `list_tracked`. Tree walks
   never descend into symlinked directories.
2. **Bounded upward walks.** `find_enclosing_vcs` in
   [`dotfiles/vcs.py`](./dotfiles/vcs.py) stops at `cfg.home`, so it
   can't wander outside the user's scope.
3. **Single-hop `readlink` in eject.** `fs.restore_from_symlink` reads
   the link exactly once — it does not chase chained symlinks.
4. **Self-referential symlink guard.** `fs.make_symlink` refuses if the
   link path equals the target or if the target lives inside the link's
   own subtree (which would loop the moment the directory is entered).
5. **Already-tracked short-circuit.** `plan_add` detects when the source
   is already a symlink into the repo and returns a no-op plan before
   any walk happens — re-adding a tracked directory never re-walks it.
6. **Depth cap** (`Config.max_depth`, default 64) on directory walks so
   pathological trees fail fast with a clear error.
7. **Source-contains-repo check.** `plan_add` refuses when the source
   path equals or contains `cfg.repo_path`. Keeping the repo under
   `$HOME` (e.g. `~/.dotfiles-repo`) is a common convention and is
   allowed; the check only fires on the actual operation that would
   move the repo into itself.

## Configuration discovery

Precedence (high to low):

1. `--config PATH` flag.
2. `DOTFILES_CONFIG` environment variable.
3. `$XDG_CONFIG_HOME/dotfiles/config.toml`.
4. `~/.config/dotfiles/config.toml`.

Implemented by `config.resolve_config_path` /
`config.load_config`. The CLI loads once and threads `Config` through.

## Testing philosophy

* Pure functions (`paths`, `plan_*`, predicates) are tested with no
  mocks — just data.
* `fs.py` is tested against a real `tmp_path` filesystem. We do not mock
  `os.symlink`; the real behaviour is cheap and reliable enough.
* `vcs.py`'s `git_add` is tested end-to-end against a real `git init`
  in `tmp_path` — no `subprocess.run` mocking.
* The CLI is tested via `typer.testing.CliRunner` with a config file
  written into `tmp_path`.
