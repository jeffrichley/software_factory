"""HTTP API: event ingestion, dashboard state as JSON and over SSE, and the static dashboard."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import states
from .activity import running_skill, started_skill, tool_headline
from .github import GitHub, read_issues
from .silence import as_shown, is_silent
from .skills import DEFAULT_SKILL_TABLE, SkillTable, bare_name, skill_invocation, work_item_named
from .store import Store
from .work_items import pull_requests, work_items

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
    # Sent with SessionStart only: the installed mattpocock-skills version, for the skill table's version ranges.
    mattpocock_skills_version: str | None = None
    # Set on an event that was queued while the server was down: when it happened on the Machine.
    queued_at: datetime | None = None


class Reply(BaseModel):
    session_id: str | None
    job_id: str | None = None
    step_id: str | None = None
    server_version: str = SERVER_VERSION
    inject: str | None = None


class Broadcaster:
    """Fans each dashboard state change out to every open SSE stream."""

    def __init__(self) -> None:
        self.queues: dict[asyncio.Queue[dict], asyncio.AbstractEventLoop] = {}

    def publish(self, state: dict) -> None:
        """Safe from any thread: each queue is filled on its own stream's event loop."""
        for q, loop in list(self.queues.items()):
            loop.call_soon_threadsafe(q.put_nowait, state)

    async def stream(self, current: Callable[[], dict], refresh_s: float) -> AsyncIterator[str]:
        """Sends the state now and on every change; between events, rechecks it every `refresh_s`
        so a Machine going silent reaches the dashboard without an event of its own."""
        q: asyncio.Queue[dict] = asyncio.Queue()
        self.queues[q] = asyncio.get_running_loop()
        try:
            state, sent = current(), None
            while True:
                if state != sent:
                    yield f"event: state\ndata: {json.dumps(state)}\n\n"
                    sent = state
                try:
                    state = await asyncio.wait_for(q.get(), refresh_s)
                except TimeoutError:
                    state = current()
        finally:
            self.queues.pop(q, None)


def create_app(
    db_path: Path,
    github: GitHub,
    clock: Callable[[], datetime],
    skill_table: Path = DEFAULT_SKILL_TABLE,
    refresh_s: float = 5,
) -> FastAPI:
    store = Store(db_path)
    skills = SkillTable(skill_table)
    hub = Broadcaster()
    polled_at: dict[str, datetime] = {}

    def state() -> dict:
        now = clock()
        machines = [{**m, "silent": is_silent(m["last_seen"], now)} for m in store.machines()]
        silent_since = {m["machine"]: m["last_seen"] for m in machines if m["silent"]}
        return {
            "server_version": SERVER_VERSION,
            "machines": machines,
            "repos": store.tracked_repos(),
            "sessions": [as_shown(s, silent_since.get(s["machine"])) for s in store.live_sessions()],
            "work_items": store.work_items(),
            "pull_requests": store.pull_requests(),
            "mismatches": mismatches(),
        }

    def mismatches() -> list[dict]:
        """Skill starts in live sessions against the wrong kind of Work item."""
        found = []
        for start in store.live_skill_starts():
            role = skills.role(start["skill"], start.pop("mattpocock_skills_version"))
            expected = list(role.work_items) if role else []
            if expected and start["kind"] and start["kind"] not in expected:
                found.append({**start, "expected": expected})
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

    def poll_once() -> None:
        """Read every due repo from GitHub (blocking). A repo whose read or save fails keeps its last poll."""
        for repo in due():
            try:
                issues = read_issues(github, repo)
                store.save_poll(repo, work_items(repo, issues), pull_requests(issues))
                hub.publish(state())
            except Exception:
                log.exception("GitHub poll of %s failed", repo)

    async def poll_forever() -> None:
        while True:
            await asyncio.to_thread(poll_once)
            await asyncio.sleep(POLL_CHECK_SECONDS)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(poll_forever())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    app = FastAPI(title="Factory server", version=SERVER_VERSION, lifespan=lifespan)
    # Tests call the poller by hand with a fake clock, instead of running the background loop.
    app.state.poll_once = poll_once

    def observe(session_id: int, event: dict, now: datetime) -> None:
        """Kind, headline and timeline from what the session does."""
        if invocation := skill_invocation(event):
            skill = invocation[0]
            name = bare_name(skill)  # Matt's skills go by their table name, without the plugin prefix
            role = skills.role(name, store.session(session_id)["mattpocock_skills_version"]) if name else None
            if role is None:
                # Recorded even inside a Job or a subagent; it labels the session only while it is ad hoc.
                store.record_unknown_skill(session_id, skill, now)
                store.record_action(session_id, running_skill(skill), now)
                return
            # A subagent's skills (an implementer's tdd) belong to its parent's Job: they never reclassify the session.
            if role.kind and "agent_id" not in event:
                store.classify(session_id, role.kind, name)
            store.record_action(session_id, started_skill(name), now)
        elif event.get("hook_event_name") == "PreToolUse":
            store.record_action(session_id, tool_headline(event), now)

    @app.post("/api/events")
    async def ingest(envelope: Envelope) -> Reply:
        event = envelope.event
        # The Machine reports now, but a queued event counts from when it happened (never later than now).
        store.machine_seen(envelope.machine, clock())
        now = min(envelope.queued_at, clock()) if envelope.queued_at else clock()
        session_id = None
        match event.get("hook_event_name"):
            case "repo_installed":
                store.track_repo(envelope.repo, envelope.machine, envelope.repo_path, now)
            case "repo_uninstalled":
                store.untrack_repo(envelope.repo, envelope.machine, now)
                polled_at.pop(envelope.repo, None)  # so re-tracking it polls at once
            case name:
                session_id = store.touch_session(envelope.machine, envelope.repo, event["session_id"], now)
                if invocation := skill_invocation(event):
                    skill, number = bare_name(invocation[0]), work_item_named(invocation[1], envelope.repo)
                    if skill and number:
                        typed = name == "UserPromptExpansion"
                        store.record_skill_start(session_id, skill, envelope.repo, number, typed=typed)
                if name == "SessionEnd":
                    store.end_session(session_id, now)
                else:
                    # A resumed session, or one still running when its repo was uninstalled and reinstalled.
                    store.resume_session(session_id, now)
                    states.apply(store, session_id, event, now)
                if name == "SessionStart":
                    store.set_mattpocock_skills_version(session_id, envelope.mattpocock_skills_version)
                observe(session_id, event, now)
        hub.publish(state())
        return Reply(session_id=None if session_id is None else str(session_id))

    @app.post("/api/sessions/{session_id}/seen")
    async def seen(session_id: int) -> dict:
        """The human opened the session's detail: its Done is seen."""
        if not store.mark_seen(session_id):
            raise HTTPException(status_code=404, detail="no such session")
        hub.publish(state())
        return {"ok": True}

    @app.get("/api/health")
    async def health() -> dict:
        """For `factory status` / `dashboard`: is the server up, and which version."""
        return {"server_version": SERVER_VERSION}

    @app.get("/api/state")
    async def get_state() -> dict:
        return state()

    @app.get("/api/stream")
    async def stream() -> StreamingResponse:
        return StreamingResponse(hub.stream(state, refresh_s), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    if DASHBOARD_DIR.is_dir():
        app.mount("/", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")
    return app
