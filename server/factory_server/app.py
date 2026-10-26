"""HTTP API: event ingestion, dashboard state as JSON and over SSE, and the static dashboard."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .github import GitHub
from .store import Store

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SERVER_VERSION: str = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
DASHBOARD_DIR = PLUGIN_ROOT / "dashboard" / "dist"


class Envelope(BaseModel):
    """A hook event (or CLI self-report) stamped with where it came from."""

    machine: str
    repo: str
    repo_path: str
    ids: dict = {}
    event: dict


class Reply(BaseModel):
    session_id: str | None
    job_id: str | None = None
    step_id: str | None = None
    server_version: str = SERVER_VERSION
    inject: str | None = None


class Broadcaster:
    """Fans each dashboard state change out to every open SSE stream."""

    def __init__(self) -> None:
        self.queues: set[asyncio.Queue[dict]] = set()

    def publish(self, state: dict) -> None:
        for q in self.queues:
            q.put_nowait(state)

    async def stream(self, first: dict) -> AsyncIterator[str]:
        q: asyncio.Queue[dict] = asyncio.Queue()
        self.queues.add(q)
        try:
            state = first
            while True:
                yield f"event: state\ndata: {json.dumps(state)}\n\n"
                state = await q.get()
        finally:
            self.queues.discard(q)


def create_app(db_path: Path, github: GitHub, clock: Callable[[], datetime]) -> FastAPI:
    # github is unused until the poller arrives; it is injected now so the seam is fixed.
    store = Store(db_path)
    hub = Broadcaster()
    app = FastAPI(title="Factory server", version=SERVER_VERSION)

    def state() -> dict:
        return {"server_version": SERVER_VERSION, "repos": store.tracked_repos(), "sessions": store.live_sessions()}

    @app.post("/api/events")
    async def ingest(envelope: Envelope) -> Reply:
        event = envelope.event
        now = clock()
        session_id = None
        match event.get("hook_event_name"):
            case "repo_installed":
                store.track_repo(envelope.repo, envelope.machine, envelope.repo_path, now)
            case "repo_uninstalled":
                store.untrack_repo(envelope.repo, envelope.machine, now)
            case name:
                session_id = store.touch_session(envelope.machine, envelope.repo, event["session_id"], now)
                if name == "SessionEnd":
                    store.end_session(session_id, now)
                else:
                    # A resumed session, or one still running when its repo was uninstalled and reinstalled.
                    store.resume_session(session_id, now)
        hub.publish(state())
        return Reply(session_id=None if session_id is None else str(session_id))

    @app.get("/api/health")
    async def health() -> dict:
        """For `factory status` / `dashboard`: is the server up, and which version."""
        return {"server_version": SERVER_VERSION}

    @app.get("/api/state")
    async def get_state() -> dict:
        return state()

    @app.get("/api/stream")
    async def stream() -> StreamingResponse:
        return StreamingResponse(hub.stream(state()), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    if DASHBOARD_DIR.is_dir():
        app.mount("/", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")
    return app
