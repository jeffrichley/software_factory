"""Where a Machine keeps its setup and where a repo keeps this Machine's tracking.

Stdlib only: the hook imports this on every event (ADR 0001).
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

PLUGIN_ID = "factory-software-factory"  # <plugin>-<marketplace>, as Claude Code names plugin data dirs
POST_TIMEOUT_S = 2


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


def machine_dir(main: Path, machine: str) -> Path:
    """This Machine's own directory beside its marker: session cache and event queue."""
    return factory_dir(main) / "machines" / machine


def session_cache_path(main: Path, machine: str, cc_session_id: str) -> Path:
    """The ids the server last replied with for a Claude Code session, under this Machine's own directory."""
    return machine_dir(main, machine) / "sessions" / f"{cc_session_id}.json"


def latest_session_ids(main: Path, machine: str) -> dict:
    """The ids cached for this Machine's most recently active session in the repo, or {}."""
    caches = sorted((machine_dir(main, machine) / "sessions").glob("*.json"), key=lambda p: p.stat().st_mtime)
    try:
        return json.loads(caches[-1].read_text()) if caches else {}
    except (OSError, ValueError):
        return {}


def queue_path(main: Path, machine: str) -> Path:
    """Events the server couldn't take yet, one JSON envelope per line, oldest first."""
    return machine_dir(main, machine) / "queue.jsonl"


class Refused(Exception):
    """The server answered 4xx: sending the event again can't help, so it is dropped, never queued."""


def post_event(server_url: str, body: dict) -> dict:
    """POST one envelope to the server and return its reply.

    Raises OSError when the server can't take it now (unreachable, or 5xx), and Refused on a 4xx.
    """
    req = urllib.request.Request(
        f"{server_url}/api/events", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=POST_TIMEOUT_S) as resp:
            reply = resp.read()
    except urllib.error.HTTPError as e:
        if e.code < 500:
            raise Refused(f"the server refused {body['event'].get('hook_event_name')} ({e.code}); dropped") from e
        raise
    try:
        return json.loads(reply)
    except ValueError:
        return {}  # delivered, but nothing to cache


def log_refused(e: Refused) -> None:
    print(f"factory: {e}", file=sys.stderr)


def enqueue(main: Path, machine: str, body: dict) -> None:
    """Queue an envelope, stamped with when it happened for the server to use instead of when it arrives."""
    q = queue_path(main, machine)
    q.parent.mkdir(parents=True, exist_ok=True)
    stamped = {"queued_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"), **body}
    with q.open("a") as f:
        f.write(json.dumps(stamped) + "\n")


def queued(main: Path, machine: str) -> list[str]:
    try:
        return queue_path(main, machine).read_text().splitlines()
    except OSError:
        return []


def time_left(deadline: float | None) -> bool:
    """Whether a POST can still run its full timeout before `deadline` (a time.monotonic() value; None = no limit)."""
    return deadline is None or time.monotonic() + POST_TIMEOUT_S <= deadline


def flush_queue(main: Path, machine: str, server_url: str, deadline: float | None = None) -> bool:
    """Deliver queued events in order; True once none are left.

    Stops at the first failure, or when `deadline` leaves no time for another POST, keeping the rest in order.
    """
    lines = queued(main, machine)
    for i, line in enumerate(lines):
        try:
            body = json.loads(line)
        except ValueError:
            continue  # a line half-written by a crash: drop it rather than block the queue for good
        try:
            if not time_left(deadline):
                raise TimeoutError
            post_event(server_url, body)
        except Refused as e:
            log_refused(e)  # resending can't help: drop it rather than block the queue for good
        except OSError:
            queue_path(main, machine).write_text("".join(f"{rest}\n" for rest in lines[i:]))
            return False
    queue_path(main, machine).unlink(missing_ok=True)
    return True


def send(main: Path, machine: str, server_url: str, body: dict, deadline: float | None = None) -> dict | None:
    """Deliver any queued events, then this one; queue it when the server can't take it before `deadline`.

    Returns the server's reply ({} when it refused the event), or None when the event was queued.
    """
    if flush_queue(main, machine, server_url, deadline) and time_left(deadline):
        try:
            return post_event(server_url, body)
        except Refused as e:
            log_refused(e)
            return {}
        except OSError:
            pass
    enqueue(main, machine, body)
    return None


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
