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

from . import sounds, states
from .activity import running_skill, started_skill, tool_headline
from .github import GitHub, read_issues
from .jobs import IN_PROGRESS, TICKET_JOB, ticket_job_start, worktree_of
from .phases import DEFAULT_PHASE_RULES, PHASES, PhaseRules, phase_named
from .silence import as_shown, is_silent
from .skills import DEFAULT_SKILL_TABLE, SkillTable, bare_name, skill_invocation, work_item_named
from .store import Store
from .work_items import pull_requests, work_items

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SERVER_VERSION: str = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
DASHBOARD_DIR = PLUGIN_ROOT / "dashboard" / "dist"
POLL_EVERY = timedelta(minutes=1)
POLL_CHECK_SECONDS = 5
# Sent by 'factory hide' / 'factory show' for the session that runs them: is it hidden now.
HIDE_EVENTS = dict(session_hidden=True, session_shown=False)

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
    phase_rules_path: Path = DEFAULT_PHASE_RULES,
    # Often enough that a sound whose grace runs out reaches the dashboard about on time.
    refresh_s: float = 1,
) -> FastAPI:
    store = Store(db_path)
    skills = SkillTable(skill_table)
    phase_rules = PhaseRules(phase_rules_path)
    hub = Broadcaster()
    polled_at: dict[str, datetime] = {}

    def state() -> dict:
        now = clock()
        store.release_sounds(now)
        machines = [{**m, "silent": is_silent(m["last_seen"], now)} for m in store.machines()]
        silent_since = {m["machine"]: m["last_seen"] for m in machines if m["silent"]}
        return {
            "server_version": SERVER_VERSION,
            "machines": machines,
            "repos": store.tracked_repos(),
            "sessions": [as_shown(s, silent_since.get(s["machine"])) for s in store.live_sessions()],
            "work_items": store.work_items(),
            "pull_requests": store.pull_requests(),
            "jobs": store.jobs(),
            "steps": store.steps(),
            "mismatches": mismatches(),
            "sounds": store.sounds(),
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
                prs_arrived(repo)
                prs_merged(repo)
                hub.publish(state())
            except Exception:
                log.exception("GitHub poll of %s failed", repo)

    def prs_arrived(repo: str) -> None:
        """A poll may bring the non-draft PR of a Job that already stopped without one, or end that Job."""
        for s in store.live_sessions():
            job_id = store.current_job(int(s["id"]))
            if s["repo"] == repo and job_id is not None and store.job_stage(job_id) != IN_PROGRESS:
                pr_arrived(int(s["id"]), clock())

    def prs_merged(repo: str) -> None:
        """A Job's PR merged is a signal to each of its Steps."""
        for job_id in store.merged_jobs(repo):
            session_id = store.job_session(job_id)
            for step_id in store.job_steps(job_id):
                infer_phase(step_id, job_id, "pr_merged", session_id, clock())

    def pr_arrived(session_id: int, now: datetime) -> None:
        if states.pr_no_longer_awaited(store, session_id, now):
            sounds.schedule(store, session_id, {}, now)  # a stopped Job turning Done sounds like any Done

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
        session_id = job_id = step_id = inject = None
        match event.get("hook_event_name"):
            case "repo_installed":
                store.track_repo(envelope.repo, envelope.machine, envelope.repo_path, now)
            case "repo_uninstalled":
                store.untrack_repo(envelope.repo, envelope.machine, now)
                polled_at.pop(envelope.repo, None)  # so re-tracking it polls at once
            case "report_pr" | "job_issue" | "report_phase" | "escalate" as name:
                session_id, job_id, step_id = self_report(name, event, now)
            case name:
                session_id = store.touch_session(envelope.machine, envelope.repo, event["session_id"], now)
                if name in HIDE_EVENTS:
                    store.set_hidden(session_id, HIDE_EVENTS[name])
                if invocation := skill_invocation(event):
                    skill, number = bare_name(invocation[0]), work_item_named(invocation[1], envelope.repo)
                    typed = name == "UserPromptExpansion"
                    if skill and number:
                        store.record_skill_start(session_id, skill, envelope.repo, number, typed=typed)
                    if typed and skill:
                        inject = start_job(session_id, skill, number, envelope, now)
                job_id = store.current_job(session_id)
                if job_id is not None and "agent_id" not in event:
                    follow_worktree(job_id, event, envelope.repo_path)
                if name == "SessionEnd":
                    store.end_session(session_id, now)
                else:
                    # A resumed session, or one still running when its repo was uninstalled and reinstalled.
                    store.resume_session(session_id, now)
                    without_pr = job_id is not None and store.job_stage(job_id) == IN_PROGRESS
                    states.apply(store, session_id, event, now, job_without_pr=without_pr)
                    sounds.schedule(store, session_id, event, now)
                if name == "SessionStart":
                    store.set_mattpocock_skills_version(session_id, envelope.mattpocock_skills_version)
                observe(session_id, event, now)
                step_id = step_of(job_id)
                if step_id is not None:
                    infer_phase(step_id, job_id, phase_rules.load().signal(event), session_id, now)
        hub.publish(state())
        return Reply(
            session_id=None if session_id is None else str(session_id),
            job_id=None if job_id is None else str(job_id),
            step_id=None if step_id is None else str(step_id),
            inject=inject,
        )

    def step_of(job_id: int | None) -> int | None:
        """The Step an event of the Job belongs to: a Ticket Job's one Step."""
        if job_id is None or store.job_kind(job_id) != TICKET_JOB:
            return None
        return next(iter(store.job_steps(job_id)), None)

    def infer_phase(step_id: int, job_id: int, signal: str | None, session_id: int, now: datetime) -> None:
        """The Step's Phase after a signal, by the Phase rules."""
        if signal is None:
            return
        version = store.session(session_id)["mattpocock_skills_version"]
        to = phase_rules.load().next_phase(store.step_phase(step_id), signal, store.job_kind(job_id), version)
        if to is not None:
            store.set_phase(step_id, to, now)

    def start_job(session_id: int, skill: str, number: int | None, envelope: Envelope, now: datetime) -> str | None:
        """A typed Job skill starts a new Job (older ones carry on); returns what to tell the agent."""
        role = skills.role(skill, store.session(session_id)["mattpocock_skills_version"])
        if role is None or role.role != TICKET_JOB:
            return None
        job_id = store.start_job(session_id, role.role, envelope.repo, number, now)
        store.add_step(job_id, number, now)  # a Ticket Job's one Step works its Ticket
        item = store.work_item(envelope.repo, number) if number else None
        worktree = worktree_of(envelope.event.get("cwd"), envelope.repo_path)
        duplicate_of = store.duplicate_of(job_id)
        return ticket_job_start(str(job_id), number, item and item["title"], worktree,
                                duplicate_of=None if duplicate_of is None else str(duplicate_of))

    def follow_worktree(job_id: int, event: dict, main_tree: str) -> None:
        """Where the Job works: the worktree EnterWorktree made, else the session's own cwd when in one."""
        response = event.get("tool_response") if isinstance(event.get("tool_response"), dict) else {}
        if event.get("hook_event_name") == "PostToolUse" and event.get("tool_name") == "EnterWorktree" and response.get("worktreePath"):
            store.set_job_worktree(job_id, response["worktreePath"], response.get("worktreeBranch"))
        elif worktree := worktree_of(event.get("cwd"), main_tree):
            store.set_job_worktree(job_id, worktree)

    def self_report(name: str, event: dict, now: datetime) -> tuple[int, int, int | None]:
        """A `factory` self-report about a Job; every one names its Job."""
        try:
            job_id = int(event.get("job_id"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="a self-report needs --job <id>") from None
        session_id = store.job_session(job_id)
        if session_id is None:
            raise HTTPException(status_code=404, detail=f"no Job {job_id}")
        step_id = step_of(job_id)
        match name:
            case "report_pr":
                store.set_job_pr(job_id, str(event.get("url") or ""))
            case "job_issue":
                if not str(event.get("issue", "")).isdigit():
                    raise HTTPException(status_code=422, detail="`factory job` needs --issue <number>")
                store.set_job_number(job_id, int(event["issue"]))
            case "report_phase":
                step_id = report_phase(job_id, event, now)
            case "escalate":
                states.escalate(store, session_id, str(event.get("reason") or ""), now)
                sounds.schedule(store, session_id, event, now)
        if store.current_job(session_id) == job_id and store.job_stage(job_id) != IN_PROGRESS:
            pr_arrived(session_id, now)
        return session_id, job_id, step_id

    def report_phase(job_id: int, event: dict, now: datetime) -> int:
        """`factory phase <name>`: the Step's Phase as its agent says, for when the rules can't tell."""
        phase = phase_named(str(event.get("phase") or ""))
        if phase is None:
            raise HTTPException(status_code=422, detail=f"`factory phase` needs one of {', '.join(PHASES)}")
        ticket = event.get("ticket")
        if ticket is None:
            step_id = step_of(job_id)
        elif str(ticket).isdigit():
            step_id = store.job_step_numbered(job_id, int(ticket))
        else:
            raise HTTPException(status_code=422, detail="--ticket needs an issue number")
        if step_id is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} has no Step" + (f" for #{ticket}" if ticket else ""))
        store.set_phase(step_id, phase, now)
        return step_id

    @app.post("/api/jobs/{job_id}/abandon")
    async def abandon(job_id: int) -> dict:
        """The human abandoned the Job on the dashboard: it moves to History, and its session waits for no PR."""
        if not store.abandon_job(job_id, clock()):
            raise HTTPException(status_code=404, detail="no such Job")
        session_id = store.job_session(job_id)
        if store.current_job(session_id) == job_id:
            states.pr_no_longer_awaited(store, session_id, clock(), seen=True)
        hub.publish(state())
        return {"ok": True}

    @app.post("/api/sessions/{session_id}/seen")
    async def seen(session_id: int) -> dict:
        """The human opened the session's detail: its Done is seen."""
        if not store.mark_seen(session_id):
            raise HTTPException(status_code=404, detail="no such session")
        hub.publish(state())
        return {"ok": True}

    @app.post("/api/sessions/{session_id}/hide")
    async def hide(session_id: int) -> dict:
        """The human hid the session from the dashboard: out of its views, and silent."""
        return set_hidden(session_id, True)

    @app.post("/api/sessions/{session_id}/show")
    async def show(session_id: int) -> dict:
        return set_hidden(session_id, False)

    def set_hidden(session_id: int, hidden: bool) -> dict:
        if not store.set_hidden(session_id, hidden):
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
