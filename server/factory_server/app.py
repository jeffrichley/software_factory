"""HTTP API: event ingestion, dashboard state as JSON and over SSE, and the static dashboard."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .github import GitHub, read_issues
from .store import Store
from .work_items import expected_kinds, pull_requests, skill_run, work_items

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SERVER_VERSION: str = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
DASHBOARD_DIR = PLUGIN_ROOT / "dashboard" / "dist"
POLL_EVERY = timedelta(minutes=1)
POLL_CHECK_SECONDS = 5

log = logging.getLogger(__name__)


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
    store = Store(db_path)
    hub = Broadcaster()
    polled_at: dict[str, datetime] = {}

    def state() -> dict:
        return {
            "server_version": SERVER_VERSION,
            "repos": store.tracked_repos(),
            "sessions": store.live_sessions(),
            "work_items": store.work_items(),
            "pull_requests": store.pull_requests(),
            "mismatches": mismatches(),
        }

    def mismatches() -> list[dict]:
        """Skill runs in live sessions against the wrong kind of Work item."""
        found = []
        for run in store.live_skill_runs():
            expected = expected_kinds(run["skill"], run["kind"])
            if expected:
                found.append({**run, "expected": expected})
        return found

    def due() -> list[str]:
        """Tracked repos not polled in the last minute, marked as polled now; a repo no Machine tracks is never due.

        A failed read still counts, so GitHub is retried a minute later rather than hammered.
        """
        now = clock()
        repos = [r["repo"] for r in store.tracked_repos() if repo_due(r["repo"], now)]
        polled_at.update(dict.fromkeys(repos, now))
        return repos

    def repo_due(repo: str, now: datetime) -> bool:
        return repo not in polled_at or now - polled_at[repo] >= POLL_EVERY

    def save(repo: str, issues: list[dict]) -> None:
        store.save_poll(repo, work_items(repo, issues), pull_requests(issues))
        hub.publish(state())

    def poll() -> None:
        """Read every due repo from GitHub. A failed read keeps the last poll's state."""
        for repo in due():
            try:
                issues = read_issues(github, repo)
            except Exception:
                log.exception("GitHub poll of %s failed", repo)
                continue
            save(repo, issues)

    async def poll_forever() -> None:
        """poll(), with each `gh api` read off the event loop."""
        while True:
            for repo in due():
                try:
                    issues = await asyncio.to_thread(read_issues, github, repo)
                except Exception:
                    log.exception("GitHub poll of %s failed", repo)
                    continue
                save(repo, issues)
            await asyncio.sleep(POLL_CHECK_SECONDS)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(poll_forever())
        yield
        task.cancel()

    app = FastAPI(title="Factory server", version=SERVER_VERSION, lifespan=lifespan)
    # Tests drive the poller by hand with a fake clock, instead of running the background loop.
    app.state.poll = poll

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
                if run := skill_run(event):
                    skill, number = run
                    store.record_skill_run(session_id, skill, envelope.repo, number)
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
