"""Module entry point: ``python -m dotfiles`` delegates to the Typer app."""

from .cli import app


if __name__ == "__main__":
    app()
