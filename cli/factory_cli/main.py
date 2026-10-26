"""The `factory` CLI."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from .tracking import data_dir, github_repo, load_setup, machine_dir, main_worktree, marker_path, save_setup

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORT = 47821

app = typer.Typer(no_args_is_help=True, add_completion=False)


def factory_version() -> str:
    return json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]


def fail(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(1)


@app.command()
def setup(
    machine: Annotated[str, typer.Option(prompt="Name this Machine (e.g. wsl, windows, mac)")],
    server: Annotated[str, typer.Option(prompt="Factory server URL", help="e.g. http://mac.local:47821")],
) -> None:
    """Name this Machine and set the Factory server's address."""
    save_setup(machine, server)
    typer.echo(f"This Machine is '{machine}', reporting to {server}.")


@app.command()
def install() -> None:
    """Turn the current repo on for this Machine."""
    setup = load_setup()
    if not setup:
        fail("This Machine isn't set up yet. Run `factory setup` first.")
    main = main_worktree(Path.cwd())
    if not main:
        fail("Not inside a git repo.")
    machine = setup["machine"]
    marker = marker_path(main, machine)
    if marker.exists():
        typer.echo(f"Already tracked on '{machine}': {main}")
        return
    factory_dir = main / ".factory"
    factory_dir.mkdir(exist_ok=True)
    (factory_dir / ".gitignore").write_text("*\n")
    machine_dir(main, machine).parent.mkdir(exist_ok=True)
    marker.write_text(json.dumps({
        "installed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "factory_version": factory_version(),
        "repo": github_repo(main) or main.name,
    }, indent=2))
    typer.echo(f"Tracking {main} on '{machine}'.")


@app.command()
def server(
    port: Annotated[int, typer.Option(help="Port to listen on.")] = DEFAULT_PORT,
    host: Annotated[str, typer.Option(help="Interface to bind; 0.0.0.0 serves the whole local network.")] = "0.0.0.0",
    db: Annotated[Path | None, typer.Option(help="SQLite file.")] = None,
) -> None:
    """Run the Factory server in the foreground."""
    import sys

    import uvicorn

    sys.path.insert(0, str(PLUGIN_ROOT / "server"))
    from factory_server import GhCli, create_app

    db = db or data_dir() / "server" / "factory.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Factory server on http://{host}:{port} (state in {db})")
    uvicorn.run(create_app(db_path=db, github=GhCli(), clock=lambda: datetime.now(UTC)), host=host, port=port)
