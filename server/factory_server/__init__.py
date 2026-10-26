"""The Factory server: ingests events from every Machine and serves the dashboard."""

from .app import SERVER_VERSION, create_app
from .github import GhCli
from .skills import DEFAULT_SKILL_TABLE

__all__ = ["DEFAULT_SKILL_TABLE", "SERVER_VERSION", "GhCli", "create_app"]
