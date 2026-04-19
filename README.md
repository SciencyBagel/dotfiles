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
allowed_paths = [
    "/home/alice/.oh-my-zsh/custom",   # user plugins inside an ignored repo
]
auto_stage = false
detect_nested_vcs = true
trust_nested_gitignore = true
relative_symlinks = false
```

## Nested repos (oh-my-zsh, LazyVim, rustup, …)

`dotfiles add` refuses by default if the source lives inside an
unrelated git repo — tracking a vendor-owned file would fight with
that repo's own history. Two escape hatches make the common cases
friction-free:

1. **`allowed_paths` — declarative hole-punch.** Any path under an
   `allowed_paths` entry is exempt from both `ignored_paths` and the
   nested-VCS check. Use it for extension points that third-party
   repos *expect* you to write into:

   ```toml
   ignored_paths = ["~/.oh-my-zsh"]
   allowed_paths = ["~/.oh-my-zsh/custom"]
   ```

2. **`trust_nested_gitignore = true` (default).** When a nested repo
   is detected, the tool asks `git check-ignore` whether that repo
   already ignores the file. If it does, tracking it here cannot
   cause a conflict, so the `add` is allowed with a one-line note.
   This makes the oh-my-zsh `custom/` case zero-config — oh-my-zsh's
   own `.gitignore` already excludes it.

Set `trust_nested_gitignore = false` to require explicit
`allowed_paths` entries for every exception.

## Design

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for how the code is organised,
the plan/execute split, safety-net contract, and loop-safety guarantees.
