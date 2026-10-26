"""The Factory server: ingests events from every Machine and serves the dashboard."""

from .app import SERVER_VERSION, create_app
from .github import GhCli

__all__ = ["SERVER_VERSION", "GhCli", "create_app"]
