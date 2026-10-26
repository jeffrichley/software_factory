"""Where a Machine keeps its setup and where a repo keeps this Machine's tracking.

Stdlib only: the hook imports this on every event (ADR 0001).
"""

import json
import os
import re
import subprocess
from pathlib import Path

PLUGIN_ID = "factory-software-factory"  # <plugin>-<marketplace>, as Claude Code names plugin data dirs


def data_dir() -> Path:
    """The Factory's persistent data directory, which survives plugin updates.

    Always the marketplace install's directory, never $CLAUDE_PLUGIN_DATA: the CLI in a plain
    shell can't see that variable, and a `--plugin-dir` session points it somewhere else.
    """
    claude = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return claude / "plugins" / "data" / PLUGIN_ID


def load_setup() -> dict | None:
    """This Machine's {machine, server_url}, or None before `factory setup`."""
    try:
        return json.loads((data_dir() / "setup.json").read_text())
    except (OSError, ValueError):
        return None


def save_setup(machine: str, server_url: str) -> None:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "setup.json").write_text(json.dumps({"machine": machine, "server_url": server_url.rstrip("/")}, indent=2))


def main_worktree(cwd: str | Path) -> Path | None:
    """The repo's main working tree, from the main tree or any linked worktree; None outside git."""
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    common = Path(out)
    return common.parent.resolve() if common.name == ".git" else None


def factory_dir(main: Path) -> Path:
    """`.factory/` in the main working tree: per-Machine tracking, git-ignored by its own `.gitignore`."""
    return main / ".factory"


def marker_path(main: Path, machine: str) -> Path:
    """This Machine's marker: present means the repo is Tracked on this Machine."""
    return factory_dir(main) / "machines" / f"{machine}.json"


def session_cache_path(main: Path, machine: str, cc_session_id: str) -> Path:
    """The ids the server last replied with for a Claude Code session, under this Machine's own directory."""
    return factory_dir(main) / "machines" / machine / "sessions" / f"{cc_session_id}.json"


def github_repo(main: Path) -> str | None:
    """`owner/repo` from origin when it is on GitHub."""
    try:
        url = subprocess.run(
            ["git", "-C", str(main), "remote", "get-url", "origin"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return m.group(1) if m else None
