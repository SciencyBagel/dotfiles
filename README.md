# dotfiles

A small CLI for curating which files in `$HOME` are kept under git version
control. It moves the real file into a dedicated git repo and leaves a
symlink at the original location.

## Install

```
pip install -e .
```

Requires Python 3.11+.

## Quickstart

```bash
# Scaffold a tracked repo and create ~/.config/dotfiles/config.toml
dotfiles init --repo ~/.dotfiles-repo

# Track a file: moves ~/.zshrc into the repo and leaves a symlink behind
dotfiles add ~/.zshrc --stage

# See what is tracked and whether each symlink is healthy
dotfiles list
dotfiles status

# Restore a file: replace the symlink with the real file again.
# The tracked repo is left untouched.
dotfiles eject ~/.zshrc
```

## Commands

| Command        | What it does                                                          |
|----------------|-----------------------------------------------------------------------|
| `init`         | Create the tracked repo and a starter config.                         |
| `add <path>`   | Move a home-side file into the repo and replace it with a symlink.    |
| `eject <path>` | Replace a tracked symlink with the real file. Repo untouched.         |
| `list`         | List every tracked file with its health status.                       |
| `status`       | Summarise health counts: ok / broken / replaced / missing.            |
| `restore-all`  | On a fresh machine, (re)create every symlink from the repo.           |
| `eject-all`    | Inverse of `restore-all`. Bulk eject with confirmation.               |
| `doctor`       | Report broken symlinks and config problems.                           |

All mutating commands support `--dry-run`. `restore-all` and `eject-all`
require `--yes` (or an interactive confirmation) before touching anything.

## Configuration

Default location: `~/.config/dotfiles/config.toml`. Override with
`--config PATH` or the `DOTFILES_CONFIG` environment variable.

Example:

```toml
repo_path = "/home/alice/.dotfiles-repo"
repo_subdir = "home"
ignored_paths = [
    "/home/alice/.oh-my-zsh",     # has its own .git
    "/home/alice/.config/nvim",   # LazyVim
]
auto_stage = false
detect_nested_vcs = true
relative_symlinks = false
```

## Design

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for how the code is organised,
the plan/execute split, safety-net contract, and loop-safety guarantees.
