"""The `factory` CLI."""

import json
import re
import shutil
import subprocess
import sys
import urllib.request
import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from .tracking import (
    Refused, data_dir, factory_dir, flush_queue, github_repo, latest_session, latest_session_ids, load_setup, log_refused, machine_dir,
    main_worktree, marker_path, post_event, queued, save_setup, send,
)

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORT = 47821
# uv 0.5.17 added script lockfiles (`uv lock --script`), which the CLI's committed lock needs (ADR 0001).
MIN_UV = (0, 5, 17)
# What /setup-matt-pocock-skills writes; its presence means the repo is configured for Matt's skills.
SKILLS_CONFIG = "docs/agents/issue-tracker.md"
ORIGIN_HEAD_WARNING = (
    f"Warning: {SKILLS_CONFIG} isn't on origin/HEAD, so Job worktrees (branched from there) won't see the skills "
    "config. Commit and push it (if it is pushed, run `git fetch` and `git remote set-head origin --auto`)."
)
START_SERVER = f"Start it on the Machine that hosts it with `factory server` (port {DEFAULT_PORT} unless --port)."

app = typer.Typer(no_args_is_help=True, add_completion=False)


def factory_version() -> str:
    return json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]


def fail(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(1)


def require_setup() -> dict:
    setup = load_setup()
    if not setup:
        fail("This Machine isn't set up yet. Run `factory setup` (or /factory:setup) first.")
    return setup


def require_repo() -> Path:
    main = main_worktree(Path.cwd())
    if not main:
        fail("Not inside a git repo.")
    return main


def uv_problem() -> str | None:
    """Why the uv on PATH can't run the Factory's hooks, or None when it can."""
    uv = shutil.which("uv")
    if not uv:
        return "uv isn't on PATH, and every Factory hook runs through it. Install uv: https://docs.astral.sh/uv/"
    try:
        out = subprocess.run([uv, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return f"`{uv} --version` failed, and every Factory hook runs through uv."
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    if not m or tuple(map(int, m.groups())) < MIN_UV:
        return f"{out or 'uv'} is too old: the Factory needs uv {'.'.join(map(str, MIN_UV))} or newer. Run `uv self update`."
    return None


def skills_config_pushed(main: Path) -> bool:
    """Is the skills config on origin/HEAD, where Job worktrees branch from?"""
    done = subprocess.run(
        ["git", "-C", str(main), "cat-file", "-e", f"origin/HEAD:{SKILLS_CONFIG}"], capture_output=True
    )
    return done.returncode == 0


def server_version(server_url: str) -> str | None:
    """The server's version, or None when it can't be reached."""
    try:
        with urllib.request.urlopen(f"{server_url}/api/health", timeout=2) as resp:
            return json.loads(resp.read())["server_version"]
    except (OSError, ValueError, KeyError):
        return None


def tracking_event(name: str, main: Path, machine: str, repo: str) -> dict:
    return {"machine": machine, "repo": repo, "repo_path": str(main), "ids": {}, "event": {"hook_event_name": name}}


def print_status(setup: dict, main: Path | None) -> None:
    machine, url = setup["machine"], setup["server_url"]
    typer.echo(f"Machine '{machine}', reporting to {url}")
    if main:
        marker = marker_path(main, machine)
        if marker.exists():
            installed_at = json.loads(marker.read_text()).get("installed_at", "?")
            typer.echo(f"Tracked on '{machine}' since {installed_at}: {main}")
        else:
            typer.echo(f"Not tracked on '{machine}': {main}. Run `factory install` (or /factory:install) to track it.")
        others = sorted(p.stem for p in marker.parent.glob("*.json") if p.stem != machine)
        if others:
            typer.echo(f"Also tracked on: {', '.join(others)}")
    else:
        typer.echo("Not inside a git repo.")

    version = server_version(url)
    if version is None:
        typer.echo(f"Server unreachable at {url}. {START_SERVER}")
    else:
        typer.echo(f"Server reachable (version {version}).")
        if version != factory_version():
            typer.echo(f"Warning: the server runs Factory {version} but this Machine has {factory_version()}.")

    if main and marker_path(main, machine).exists():
        # Run from a slash command, the latest session is the one running it; from a plain shell it's only the latest.
        ids = latest_session_ids(main, machine)
        typer.echo(f"Latest session {ids.get('session_id') or '—'}, Job {ids.get('job_id') or '—'}")
        if waiting := len(queued(main, machine)):
            typer.echo(f"{waiting} event(s) queued for the server.")
        if not skills_config_pushed(main):
            typer.echo(ORIGIN_HEAD_WARNING)
    if problem := uv_problem():
        typer.echo(problem)


def alias_hint() -> str:
    if sys.platform == "win32":
        return f"Set-Alias factory '{PLUGIN_ROOT / 'bin' / 'factory.cmd'}'   # PowerShell: add to $PROFILE"
    return f"alias factory='{PLUGIN_ROOT / 'bin' / 'factory'}'   # bash/zsh: add to ~/.bashrc or ~/.zshrc"


@app.command()
def setup(
    machine: Annotated[str, typer.Option(prompt="Name this Machine (e.g. wsl, windows, mac)")],
    server: Annotated[str, typer.Option(prompt="Factory server URL", help="e.g. http://mac.local:47821")],
) -> None:
    """Name this Machine and set the Factory server's address."""
    save_setup(machine, server)
    typer.echo(f"This Machine is '{machine}', reporting to {server}.")
    typer.echo("To run `factory` from a plain terminal, add this alias (re-run setup after a plugin update):")
    typer.echo(f"  {alias_hint()}")


def announce(setup: dict, main: Path, repo: str) -> None:
    """Send `repo_installed`, queueing it when the server can't be reached."""
    url = setup["server_url"]
    if send(main, setup["machine"], url, tracking_event("repo_installed", main, setup["machine"], repo)) is None:
        typer.echo(f"Server unreachable at {url}; the repo will appear on the dashboard once it's back "
                   f"(event queued). {START_SERVER}")


@app.command()
def install() -> None:
    """Turn the current repo on for this Machine."""
    setup = require_setup()
    main = require_repo()
    machine = setup["machine"]
    marker = marker_path(main, machine)
    if marker.exists():
        # Tell the server again (a no-op there), so a repo whose first event was lost still shows up.
        announce(setup, main, json.loads(marker.read_text())["repo"])
        print_status(setup, main)
        return
    if not (main / SKILLS_CONFIG).exists():
        fail("This repo isn't configured for Matt Pocock's skills yet. Type /setup-matt-pocock-skills, then install again.")
    repo = github_repo(main)
    if not repo:
        fail("The Factory reads Work items only from GitHub, and origin isn't a GitHub remote.")
    if problem := uv_problem():
        fail(problem)

    factory_dir(main).mkdir(exist_ok=True)
    (factory_dir(main) / ".gitignore").write_text("*\n")
    marker.parent.mkdir(exist_ok=True)
    marker.write_text(json.dumps({
        "installed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "factory_version": factory_version(),
        # Stored so the hook needn't ask git on every event.
        "repo": repo,
    }, indent=2))
    typer.echo(f"Tracking {main} on '{machine}'.")
    announce(setup, main, repo)
    if not skills_config_pushed(main):
        typer.echo(ORIGIN_HEAD_WARNING)


@app.command()
def uninstall() -> None:
    """Turn the current repo off for this Machine. Repo config, worktrees and branches are left alone."""
    setup = require_setup()
    main = require_repo()
    machine, url = setup["machine"], setup["server_url"]
    marker = marker_path(main, machine)
    if not marker.exists():
        typer.echo(f"Not tracked on '{machine}': {main}. Nothing to do.")
        return
    repo = json.loads(marker.read_text())["repo"]
    delivered = False
    if flush_queue(main, machine, url):
        try:
            post_event(url, tracking_event("repo_uninstalled", main, machine, repo))
            delivered = True
        except Refused as e:
            log_refused(e)
            delivered = True  # the server answered: nothing more to deliver
        except OSError:
            pass
    if not delivered:
        lost = len(queued(main, machine))
        typer.echo(f"Server unreachable at {url}: it will keep showing this Machine's sessions in {repo}"
                   + (f", and {lost} queued event(s) are dropped." if lost else "."), err=True)

    shutil.rmtree(machine_dir(main, machine), ignore_errors=True)
    marker.unlink()
    if not any(marker.parent.iterdir()):
        shutil.rmtree(factory_dir(main))
    typer.echo(f"Stopped tracking {main} on '{machine}'.")


@app.command()
def status() -> None:
    """Show whether this repo is tracked, whether the server is reachable, and the current ids."""
    print_status(require_setup(), main_worktree(Path.cwd()))


def report_on_session(name: str, done: str) -> None:
    """Send 'name' for the session running this command, queueing it when the server can't be reached."""
    setup = require_setup()
    main = require_repo()
    machine, url = setup["machine"], setup["server_url"]
    marker = marker_path(main, machine)
    if not marker.exists():
        fail(f"Not tracked on '{machine}': {main}. Run `factory install` (or /factory:install) to track it.")
    latest = latest_session(main, machine)
    if not latest:
        fail("No session has reported from this repo on this Machine yet: run this from inside a Claude Code session.")
    cc_session_id, ids = latest
    body = {**tracking_event(name, main, machine, json.loads(marker.read_text())["repo"]), "ids": ids}
    body["event"] = {"hook_event_name": name, "session_id": cc_session_id}
    if send(main, machine, url, body) is None:
        typer.echo(f"Server unreachable at {url}; queued for when it's back. {START_SERVER}")
    typer.echo(f"Session {cc_session_id} {done}.")


@app.command()
def hide() -> None:
    """Hide the current session: off the dashboard's views, and silent."""
    report_on_session("session_hidden", "hidden")


@app.command()
def show() -> None:
    """Show the current session again."""
    report_on_session("session_shown", "shown")


@app.command()
def dashboard() -> None:
    """Open the dashboard in a browser."""
    url = require_setup()["server_url"]
    if server_version(url) is None:
        fail(f"Server unreachable at {url}. {START_SERVER}")
    typer.echo(f"Dashboard: {url}/")
    webbrowser.open(f"{url}/")


report_app = typer.Typer(no_args_is_help=True, help="Report what hooks can't see about a Job.")
app.add_typer(report_app, name="report")
JobOption = Annotated[str, typer.Option("--job", help="The Job's id, as the Factory gave it at Job start.")]


def self_report(name: str, job: str, **fields) -> None:
    """Send a self-report about a Job through the hook's event path: queued while the server is down."""
    setup = require_setup()
    main = require_repo()
    machine = setup["machine"]
    marker = marker_path(main, machine)
    if not marker.exists():
        fail(f"Not tracked on '{machine}': {main}. Run `factory install` (or /factory:install) to track it.")
    body = {
        "machine": machine, "repo": json.loads(marker.read_text())["repo"], "repo_path": str(main), "ids": {},
        "event": {"hook_event_name": name, "job_id": job, **fields},
    }
    if send(main, machine, setup["server_url"], body) is None:
        typer.echo(f"Server unreachable at {setup['server_url']}; the report is queued and goes with the next event.")
    else:
        typer.echo("Reported.")


@report_app.command("pr")
def report_pr(url: Annotated[str, typer.Argument(help="The PR's URL.")], job: JobOption) -> None:
    """The Job opened its non-draft PR."""
    self_report("report_pr", job, url=url)


@app.command("job")
def job_(issue: Annotated[int, typer.Option("--issue", help="The Work item's issue number.")], job: JobOption) -> None:
    """The Work item a Job started without one is working."""
    self_report("job_issue", job, issue=issue)


@app.command()
def escalate(reason: Annotated[str, typer.Argument(help="Why the Job needs the human.")], job: JobOption) -> None:
    """The Job is stopping to ask the human for approval or help: it shows as Needs you with this reason."""
    self_report("escalate", job, reason=reason)


@app.command()
def server(
    port: Annotated[int, typer.Option(help="Port to listen on.")] = DEFAULT_PORT,
    host: Annotated[str, typer.Option(help="Interface to bind; 0.0.0.0 serves the whole local network.")] = "0.0.0.0",
    db: Annotated[Path | None, typer.Option(help="SQLite file.")] = None,
    skill_table: Annotated[
        Path | None, typer.Option(help="Skill table (TOML). Default: server/skills.toml in the data dir if present, else the shipped one.")
    ] = None,
) -> None:
    """Run the Factory server in the foreground."""
    import uvicorn

    sys.path.insert(0, str(PLUGIN_ROOT / "server"))
    from factory_server import DEFAULT_SKILL_TABLE, GhCli, create_app

    db = db or data_dir() / "server" / "factory.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    # An edited copy in the data dir survives plugin updates; the shipped table is the fallback.
    edited = data_dir() / "server" / "skills.toml"
    skill_table = skill_table or (edited if edited.is_file() else DEFAULT_SKILL_TABLE)
    typer.echo(f"Factory server on http://{host}:{port} (state in {db}, skill table {skill_table})")
    app_ = create_app(db_path=db, github=GhCli(), clock=lambda: datetime.now(UTC), skill_table=skill_table)
    uvicorn.run(app_, host=host, port=port)
