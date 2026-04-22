"""dotfiles: a small CLI for curating which files in ``$HOME`` live under git.

Overview
--------
The tool replaces a real file in ``$HOME`` with a symlink and moves the
original into a dedicated git repository. The repo mirrors the home tree
under a configurable subdirectory (``home/`` by default), so
``~/.config/nvim/init.lua`` becomes ``<repo>/home/.config/nvim/init.lua``.
"""

__version__ = "0.3.0"
