# Project: dotfiles

## Instructions

- Below are rough descriptions of the project.
- If something is unclear, ask.
- If you have ideas for improvements, go ahead and suggest them.
- stick to functional programming whenever appropriate
- use the latest best practices, including for specific packages. Feel free to look up the documentation.
  - for example, in pydantic, use the `Annotated` method.
- make the project testable
- document your code using google docstring style

## Description

- The project should be a cli that helps me pick what dotfiles I want to keep under git version control.
- should use symlinks when the file is moved to the directory that contains the file being version controlled
- I want it to consider that some dotfiles and directories might be under existing version control
like oh-my-zsh and LazyVim.

- should be configurable and reuasable

- commands:
  - `dotifles eject`
    - should remove the symlink created for a tracked dotfile and bring back the actual file
  - `dotfiles add`
    - should add the dotfile in the home directory to the configured repo that is version controlling the files
    - replace it with a symlink
    - has an option to also stage it in the directory it got moved to
  - `dotfiles list`
    - should list the tracked dotfiles
  - and other commands that make sense for the intent of the project

- should have a config.toml for confiugrations
- use best practices for package management

## Stack

- pydantic for config validation
- setuptools

