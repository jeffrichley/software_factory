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


def machine_dir(main: Path, machine: str) -> Path:
    """This Machine's session cache and event queue."""
    return main / ".factory" / "machines" / machine


def marker_path(main: Path, machine: str) -> Path:
    return main / ".factory" / "machines" / f"{machine}.json"


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
