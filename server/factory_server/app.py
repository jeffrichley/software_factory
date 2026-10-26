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

from .activity import running_skill, started_skill, tool_headline
from .github import GitHub
from .skills import DEFAULT_SKILL_TABLE, SkillTable, bare_name
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
    # Sent with SessionStart only: the installed mattpocock-skills version, for the skill table's version ranges.
    mattpocock_skills_version: str | None = None


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


def skill_started(event: dict) -> str | None:
    """The skill an event starts: typed as `/<skill>` (UserPromptExpansion) or invoked by the model (PreToolUse(Skill))."""
    match event.get("hook_event_name"):
        case "UserPromptExpansion" if event.get("expansion_type", "slash_command") == "slash_command":
            return event.get("command_name") or None
        case "PreToolUse" if event.get("tool_name") == "Skill":
            return (event.get("tool_input") or {}).get("skill") or None
    return None


def create_app(
    db_path: Path, github: GitHub, clock: Callable[[], datetime], skill_table: Path = DEFAULT_SKILL_TABLE
) -> FastAPI:
    # github is unused until the poller arrives; it is injected now so the seam is fixed.
    store = Store(db_path)
    skills = SkillTable(skill_table)
    hub = Broadcaster()
    app = FastAPI(title="Factory server", version=SERVER_VERSION)

    def state() -> dict:
        return {"server_version": SERVER_VERSION, "repos": store.tracked_repos(), "sessions": store.live_sessions()}

    def observe(session_id: int, event: dict, now: datetime) -> None:
        """Kind, headline and timeline from what the session does."""
        if skill := skill_started(event):
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
                if name == "SessionStart":
                    store.set_mattpocock_skills_version(session_id, envelope.mattpocock_skills_version)
                observe(session_id, event, now)
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
