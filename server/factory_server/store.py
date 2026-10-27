"""SQLite state: stdlib sqlite3, no ORM."""

import functools
import json
import re
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .jobs import ENDED, SPEC_JOB, pr_stage, stage_of
from .step_detail import CHURN_EDITS, KEEP_RUNS, struggle_of
from .skills import AD_HOC
from .wayfinder import mode_of

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY,
  machine TEXT NOT NULL,
  repo TEXT NOT NULL,
  cc_session_id TEXT NOT NULL,
  state TEXT NOT NULL,
  state_since TEXT NOT NULL,
  ended_at TEXT,
  UNIQUE (machine, cc_session_id)
);
CREATE TABLE IF NOT EXISTS tracking (
  repo TEXT NOT NULL,
  machine TEXT NOT NULL,
  repo_path TEXT NOT NULL,
  installed_at TEXT NOT NULL,
  PRIMARY KEY (repo, machine)
);
CREATE TABLE IF NOT EXISTS machines (
  machine TEXT PRIMARY KEY,
  last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES sessions (id),
  at TEXT NOT NULL,
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS actions_by_session ON actions (session_id, id);
-- Every start of a skill the skill table does not know, kept for good (the timeline drops old actions).
CREATE TABLE IF NOT EXISTS unknown_skills (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES sessions (id),
  skill TEXT NOT NULL,
  at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS work_items (
  repo TEXT NOT NULL,
  number INTEGER NOT NULL,
  title TEXT NOT NULL,
  state TEXT NOT NULL,
  url TEXT NOT NULL,
  kind TEXT NOT NULL,
  PRIMARY KEY (repo, number)
);
CREATE TABLE IF NOT EXISTS pull_requests (
  repo TEXT NOT NULL,
  number INTEGER NOT NULL,
  title TEXT NOT NULL,
  state TEXT NOT NULL,
  draft INTEGER NOT NULL,
  url TEXT NOT NULL,
  PRIMARY KEY (repo, number)
);
CREATE TABLE IF NOT EXISTS skill_starts (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES sessions (id),
  skill TEXT NOT NULL,
  repo TEXT NOT NULL,
  number INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS skill_starts_session ON skill_starts (session_id);
-- A prompt waiting on the human (permission, question, plan approval, elicitation), in the main
-- session (subagent '') or one of its subagents (by agent_id). key is the tool_use_id or
-- elicitation it belongs to; NULL when a PermissionRequest matched no open call.
CREATE TABLE IF NOT EXISTS prompts (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL,
  subagent TEXT NOT NULL,
  key TEXT,
  reason TEXT NOT NULL,
  since TEXT NOT NULL
);
-- Tool calls between PreToolUse and their PostToolUse/Failure: PermissionRequest carries no
-- tool_use_id, so its prompt is tied to the open call it asks about.
CREATE TABLE IF NOT EXISTS tool_uses (
  session_id INTEGER NOT NULL,
  subagent TEXT NOT NULL,
  tool_use_id TEXT NOT NULL,
  tool_name TEXT NOT NULL,
  tool_input TEXT NOT NULL,
  PRIMARY KEY (session_id, tool_use_id)
);
-- A Job: one typed launch of a Job skill. number is NULL until the Work item is known; pr_url is the PR
-- the agent reported, if any (the poll may know it, or another one, better).
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES sessions (id),
  kind TEXT NOT NULL,
  repo TEXT NOT NULL,
  number INTEGER,
  started_at TEXT NOT NULL,
  worktree TEXT,
  branch TEXT,
  pr_url TEXT
);
CREATE INDEX IF NOT EXISTS jobs_by_session ON jobs (session_id, id);
-- A Step: one Ticket worked inside a Job. phase is NULL while unknown; phase_since is when it last changed.
CREATE TABLE IF NOT EXISTS steps (
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES jobs (id),
  number INTEGER,
  phase TEXT,
  phase_since TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS steps_by_job ON steps (job_id, id);
-- A Job's timeline for its History replay, kept for good: kind is start, phase (step_id, phase), action,
-- test_pass, test_fail, commit, review, needs, pr or end.
CREATE TABLE IF NOT EXISTS job_events (
  id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL REFERENCES jobs (id),
  at TEXT NOT NULL,
  kind TEXT NOT NULL,
  text TEXT NOT NULL,
  step_id INTEGER,
  phase TEXT
);
CREATE INDEX IF NOT EXISTS job_events_by_job ON job_events (job_id, id);
-- The Step each subagent of a Spec Job works, by the subagent's agent_id.
CREATE TABLE IF NOT EXISTS step_agents (
  job_id INTEGER NOT NULL REFERENCES jobs (id),
  agent_id TEXT NOT NULL,
  step_id INTEGER NOT NULL REFERENCES steps (id),
  PRIMARY KEY (job_id, agent_id)
);
-- Each test run in a Step, for its test pulse; passed/failed NULL when the output had no summary line.
CREATE TABLE IF NOT EXISTS test_runs (
  id INTEGER PRIMARY KEY,
  step_id INTEGER NOT NULL REFERENCES steps (id),
  at TEXT NOT NULL,
  result TEXT NOT NULL,
  passed INTEGER,
  failed INTEGER
);
CREATE INDEX IF NOT EXISTS test_runs_by_step ON test_runs (step_id, id);
-- Each file a Step's agent edited, with its edits in all and since the Step's tests last passed (for churn), and
-- the lines its edits added and deleted (NULL = unknown: some edit's patch couldn't be read).
CREATE TABLE IF NOT EXISTS step_files (
  id INTEGER PRIMARY KEY,
  step_id INTEGER NOT NULL REFERENCES steps (id),
  path TEXT NOT NULL,
  edits INTEGER NOT NULL,
  since_pass INTEGER NOT NULL,
  added INTEGER,
  deleted INTEGER,
  UNIQUE (step_id, path)
);
-- Each commit a Step's agent made, with its diffstat.
CREATE TABLE IF NOT EXISTS step_commits (
  id INTEGER PRIMARY KEY,
  step_id INTEGER NOT NULL REFERENCES steps (id),
  at TEXT NOT NULL,
  sha TEXT NOT NULL,
  message TEXT NOT NULL,
  files INTEGER NOT NULL,
  added INTEGER NOT NULL,
  deleted INTEGER NOT NULL
);
-- The CI checks on a Job's PR's head commit, as last read (JSON list of {name, status}).
CREATE TABLE IF NOT EXISTS pr_checks (
  repo TEXT NOT NULL,
  number INTEGER NOT NULL,
  checks TEXT NOT NULL,
  PRIMARY KEY (repo, number)
);
-- A Job's latest code-review findings per axis, for one Step or (step_id 0) the whole Job; source is
-- 'report' (`factory review`, which wins) or 'summary' (read from code-review's summary line).
CREATE TABLE IF NOT EXISTS reviews (
  job_id INTEGER NOT NULL REFERENCES jobs (id),
  step_id INTEGER NOT NULL,
  standards INTEGER NOT NULL,
  spec INTEGER NOT NULL,
  source TEXT NOT NULL,
  PRIMARY KEY (job_id, step_id)
);
-- A sound for one transition of a session's state, due at `due`. It plays (gets `seq`, the order the
-- dashboard plays sounds in) once due if the session is still in that transition, else it is dropped.
-- A Wayfinder session: its Map, the Decision ticket it works (NULL until it claims one) and its latest grilling
-- round's question titles (JSON list).
CREATE TABLE IF NOT EXISTS wayfinder (
  session_id INTEGER PRIMARY KEY REFERENCES sessions (id),
  map INTEGER,
  ticket INTEGER,
  questions TEXT NOT NULL DEFAULT '[]'
);
-- The Decision tickets a Wayfinder session created or closed, in order.
CREATE TABLE IF NOT EXISTS decision_tickets (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES sessions (id),
  number INTEGER NOT NULL,
  action TEXT NOT NULL,
  UNIQUE (session_id, number, action)
);
-- A research, to-spec or to-tickets session's facts so far (JSON; rules in planning.py), by the kind it ran as.
CREATE TABLE IF NOT EXISTS plans (
  session_id INTEGER NOT NULL REFERENCES sessions (id),
  kind TEXT NOT NULL,
  facts TEXT NOT NULL,
  PRIMARY KEY (session_id, kind)
);
CREATE TABLE IF NOT EXISTS sounds (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL,
  transition INTEGER NOT NULL,
  sound TEXT NOT NULL,
  due TEXT NOT NULL,
  seq INTEGER,
  UNIQUE (session_id, transition)
);
"""
# Columns added after the first release, so an existing database gains them on start.
SESSION_COLUMNS = {
    "kind": f"TEXT NOT NULL DEFAULT '{AD_HOC}'",
    "skill": "TEXT",
    "headline": "TEXT",
    "headline_detail": "TEXT",  # what the headline leaves out, e.g. the full command: shown on hover
    "mattpocock_skills_version": "TEXT",
    "terminal": "TEXT",  # where the session runs, as its SessionStart said: "tmux · factory:2", "Windows Terminal"
    "base": "TEXT NOT NULL DEFAULT 'Working'",  # the state shown when no prompt is waiting
    "base_reason": "TEXT",
    "reason": "TEXT",  # JSON reason shown with Needs you
    "seen": "INTEGER NOT NULL DEFAULT 0",  # Done has been seen by the human
    "hidden": "INTEGER NOT NULL DEFAULT 0",  # hidden by the human: out of the dashboard's views, and silent
    "transitions": "INTEGER NOT NULL DEFAULT 0",  # counts changes of shown state: a sound belongs to one
    "last_event_at": "TEXT",  # its latest event, its subagents' included: how long it has been quiet
}
WORK_ITEM_COLUMNS = {
    "parent": "INTEGER",  # the parent issue's number: a Ticket's Spec, a Decision ticket's Map
    "blocked_by": "TEXT NOT NULL DEFAULT '[]'",  # JSON list of the issues in this repo that block it
    "type": "TEXT",  # a Decision ticket's type, from its `wayfinder:<type>` label
    "assignees": "TEXT NOT NULL DEFAULT '[]'",  # JSON list of logins: a Decision ticket's claim
    "map": "TEXT",  # a Map's body as JSON: destination, fog, gists, out_of_scope
}
JOB_COLUMNS = {
    "abandoned_at": "TEXT",  # when the human abandoned the Job on the dashboard
    "duplicate_of": "INTEGER",  # the active Job already on its Work item when it started (or learnt it): flagged, not blocked
    "reviewed": "INTEGER NOT NULL DEFAULT 0",  # code-review has run in the Job: its summary line may follow
    "ended_at": "TEXT",  # when the Job was first seen Merged, Closed or Abandoned: its replay ends there
    "pr_track": "TEXT NOT NULL DEFAULT '[]'",  # JSON: each PR stage (Draft, Ready, Merged, Closed) its PR was seen reach, with when
}
STEP_COLUMNS = {
    "first_phase": "TEXT",  # the Phase it was added in (Pending, or NULL = unknown): where its replay starts
    "checklist": "TEXT",  # JSON: the agent's live checklist; NULL while it has none (no todo or task tools)
    "active_at": "TEXT",  # the Step's latest event; NULL before any
    "merged_at": "TEXT",  # a Spec Job's Step: when it was first merged into the integration branch
    "merged_sha": "TEXT",  # ...and the commit that left it on, when git printed it
}
STEP_FILE_COLUMNS = {
    "added": "INTEGER",  # lines its edits added; NULL = unknown (and for files recorded before it was kept)
    "deleted": "INTEGER",
}
PULL_REQUEST_COLUMNS = {
    "closes": "TEXT NOT NULL DEFAULT '[]'",  # JSON list of the issues its body closes
}
# The ad hoc detail view's timeline shows a session's last few actions; older ones are dropped.
KEEP_ACTIONS = 8
# The state lists the last few sounds played; a dashboard that missed more than these plays none of them late.
KEEP_SOUNDS = 20

# The `subagent` value for the main session itself.
MAIN = ""


def reason_text(reason: dict | None) -> str:
    """Why a session Needs you, in a few words for a replay."""
    match reason or {}:
        case {"kind": "permission", "tool": tool, "command": command}:
            return f"permission for {tool}: {command}"
        case {"kind": "question", "text": text}:
            return f"question: {text}"
        case {"kind": "hitl", "ticket": ticket}:
            return f"HITL ticket {ticket}"
        case {"kind": "escalation", "reason": why}:
            return f"escalation: {why}"
        case {"kind": "error", "type": kind}:
            return f"stopped on error: {kind}"
        case {"kind": "no-pr"}:
            return "ended without a PR"
    return "unknown"


def iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def locked[**P, R](method: Callable[P, R]) -> Callable[P, R]:
    """One caller at a time: the GitHub poller writes from a worker thread while requests use the event loop."""

    @functools.wraps(method)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        with args[0].lock:  # type: ignore[attr-defined]
            return method(*args, **kwargs)

    return wrapper


class Store:
    def __init__(self, path: Path) -> None:
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        tables = {r["name"] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "wayfinder_tickets" in tables and "decision_tickets" not in tables:  # its name before the glossary's
            self.db.execute("ALTER TABLE wayfinder_tickets RENAME TO decision_tickets")
        self.db.executescript(SCHEMA)
        with self.db:
            for table, columns in (("sessions", SESSION_COLUMNS), ("work_items", WORK_ITEM_COLUMNS),
                                   ("pull_requests", PULL_REQUEST_COLUMNS), ("jobs", JOB_COLUMNS), ("steps", STEP_COLUMNS),
                                   ("step_files", STEP_FILE_COLUMNS)):
                have = {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}
                for column, decl in columns.items():
                    if column not in have:
                        self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    @locked
    def touch_session(self, machine: str, repo: str, cc_session_id: str, now: datetime) -> int:
        """The server's id for a Claude Code session, creating its row (Working) on first sight."""
        with self.db:
            self.db.execute(
                "INSERT INTO sessions (machine, repo, cc_session_id, state, state_since, last_event_at)"
                " VALUES (?, ?, ?, 'Working', ?, ?)"
                # A queued event arriving late never moves the latest event back.
                " ON CONFLICT (machine, cc_session_id) DO UPDATE SET"
                " last_event_at = MAX(COALESCE(last_event_at, ''), excluded.last_event_at)",
                (machine, repo, cc_session_id, iso(now), iso(now)),
            )
        row = self.db.execute(
            "SELECT id FROM sessions WHERE machine = ? AND cc_session_id = ?", (machine, cc_session_id)
        ).fetchone()
        return row["id"]

    @locked
    def resume_session(self, session_id: int, now: datetime) -> None:
        """An ended session that is active again keeps its id: bring its row back, Working from now."""
        with self.db:
            cur = self.db.execute(
                "UPDATE sessions SET ended_at = NULL, state = 'Working', state_since = ?, base = 'Working',"
                " transitions = transitions + 1,"
                " base_reason = NULL, reason = NULL WHERE id = ? AND ended_at IS NOT NULL",
                (iso(now), session_id),
            )
            if cur.rowcount:
                self._drop_waiting(session_id)

    @locked
    def end_session(self, session_id: int, now: datetime) -> None:
        """The row ends (and stays in history); prompts it left waiting are dropped."""
        with self.db:
            self.db.execute("UPDATE sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL", (iso(now), session_id))
            self._drop_waiting(session_id)

    def _drop_waiting(self, session_id: int) -> None:
        self.db.execute("DELETE FROM prompts WHERE session_id = ?", (session_id,))
        self.db.execute("DELETE FROM tool_uses WHERE session_id = ?", (session_id,))

    @locked
    def set_mattpocock_skills_version(self, session_id: int, version: str | None) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET mattpocock_skills_version = ? WHERE id = ?", (version, session_id))

    @locked
    def set_terminal(self, session_id: int, terminal: str | None) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET terminal = ? WHERE id = ?", (terminal, session_id))

    @locked
    def session(self, session_id: int) -> sqlite3.Row:
        return self.db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()

    @locked
    def classify(self, session_id: int, kind: str, skill: str | None) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET kind = ?, skill = ? WHERE id = ?", (kind, skill, session_id))

    @locked
    def record_unknown_skill(self, session_id: int, skill: str, now: datetime) -> None:
        with self.db:
            self.db.execute("INSERT INTO unknown_skills (session_id, skill, at) VALUES (?, ?, ?)", (session_id, skill, iso(now)))

    @locked
    def record_action(self, session_id: int, text: str, now: datetime, detail: str | None = None) -> None:
        """The session's headline is now `text` (with `detail`, what it leaves out); it joins the timeline, which keeps
        the last few, and the replay of the session's current Job, which keeps them all."""
        with self.db:
            job = self.db.execute("SELECT id FROM jobs WHERE session_id = ? ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
            if job:
                self._job_event(job["id"], now, "action", text)
            self.db.execute("UPDATE sessions SET headline = ?, headline_detail = ? WHERE id = ?", (text, detail, session_id))
            self.db.execute("INSERT INTO actions (session_id, at, text) VALUES (?, ?, ?)", (session_id, iso(now), text))
            self.db.execute(
                "DELETE FROM actions WHERE session_id = ? AND id NOT IN"
                " (SELECT id FROM actions WHERE session_id = ? ORDER BY id DESC LIMIT ?)",
                (session_id, session_id, KEEP_ACTIONS),
            )

    @locked
    def live_sessions(self) -> list[dict]:
        """Live rows, Needs you first (longest waiting first), then the rest in order of first sight."""
        rows = self.db.execute(
            "SELECT id, machine, repo, cc_session_id, state, state_since, reason, seen, hidden, kind, skill, headline, headline_detail, terminal,"
            " COALESCE(last_event_at, state_since) AS last_event_at,"
            " (SELECT skill FROM unknown_skills u WHERE u.session_id = sessions.id ORDER BY u.id DESC LIMIT 1) AS unknown_skill"
            " FROM sessions WHERE ended_at IS NULL"
            " ORDER BY state != 'Needs you', CASE WHEN state = 'Needs you' THEN state_since END, id"
        ).fetchall()
        actions: dict[int, list[dict]] = {}
        for a in self.db.execute(
            "SELECT session_id, at, text FROM actions WHERE session_id IN"
            " (SELECT id FROM sessions WHERE ended_at IS NULL) ORDER BY id"
        ):
            actions.setdefault(a["session_id"], []).append({"at": a["at"], "text": a["text"]})
        return [
            {
                "id": str(r["id"]), "machine": r["machine"], "repo": r["repo"], "cc_session_id": r["cc_session_id"],
                "state": r["state"], "state_since": r["state_since"], "last_event_at": r["last_event_at"],
                "reason": r["reason"] and json.loads(r["reason"]), "seen": bool(r["seen"]), "hidden": bool(r["hidden"]),
                "kind": r["kind"], "skill": r["skill"], "unknown_skill": r["unknown_skill"], "now": r["headline"], "now_detail": r["headline_detail"],
                "actions": actions.get(r["id"], []), "terminal": r["terminal"],
            }
            for r in rows
        ]

    # ---------- Needs you and Done (rules in states.py) ----------

    @locked
    def set_base(self, session_id: int, base: str, reason: dict | None = None) -> None:
        """The state the session shows when no prompt is waiting; becoming Done makes it unseen."""
        with self.db:
            self.db.execute(
                "UPDATE sessions SET seen = CASE WHEN ? = 'Done' AND base != 'Done' THEN 0 ELSE seen END,"
                " base = ?, base_reason = ? WHERE id = ?",
                (base, base, None if reason is None else json.dumps(reason), session_id),
            )

    @locked
    def mark_seen(self, session_id: int) -> bool:
        with self.db:
            return self.db.execute("UPDATE sessions SET seen = 1 WHERE id = ?", (session_id,)).rowcount > 0

    @locked
    def set_hidden(self, session_id: int, hidden: bool) -> bool:
        with self.db:
            return self.db.execute("UPDATE sessions SET hidden = ? WHERE id = ?", (int(hidden), session_id)).rowcount > 0

    @locked
    def open_tool_use(self, session_id: int, subagent: str, tool_use_id: str, tool_name: str, tool_input: dict) -> None:
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO tool_uses VALUES (?, ?, ?, ?, ?)",
                (session_id, subagent, tool_use_id, tool_name, json.dumps(tool_input, sort_keys=True)),
            )

    @locked
    def close_tool_use(self, session_id: int, tool_use_id: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM tool_uses WHERE session_id = ? AND tool_use_id = ?", (session_id, tool_use_id))

    @locked
    def open_calls(self, session_id: int, tool_name: str) -> list[dict]:
        """The inputs of the main session's calls to that tool still awaiting their PostToolUse."""
        rows = self.db.execute(
            "SELECT tool_input FROM tool_uses WHERE session_id = ? AND subagent = ? AND tool_name = ? ORDER BY rowid",
            (session_id, MAIN, tool_name),
        )
        return [json.loads(r["tool_input"]) for r in rows]

    @locked
    def find_tool_use(self, session_id: int, subagent: str, tool_name: str, tool_input: dict) -> str | None:
        """The open call a PermissionRequest asks about: that tool, same input preferred, then one
        no prompt holds yet (so concurrent calls to one tool each get theirs), then the latest."""
        row = self.db.execute(
            "SELECT tool_use_id FROM tool_uses t WHERE session_id = ? AND subagent = ? AND tool_name = ?"
            " ORDER BY tool_input = ? DESC,"
            " EXISTS (SELECT 1 FROM prompts p WHERE p.session_id = t.session_id AND p.key = t.tool_use_id),"
            " rowid DESC LIMIT 1",
            (session_id, subagent, tool_name, json.dumps(tool_input, sort_keys=True)),
        ).fetchone()
        return row["tool_use_id"] if row else None

    @locked
    def add_prompt(self, session_id: int, subagent: str, key: str | None, reason: dict, now: datetime) -> None:
        """A prompt starts waiting, unless the same one already waits (same call, or same ask with no call)."""
        reason_json = json.dumps(reason)
        with self.db:
            if self.db.execute(
                "SELECT 1 FROM prompts WHERE session_id = ? AND (key = ? OR (? IS NULL AND key IS NULL AND subagent = ? AND reason = ?))",
                (session_id, key, key, subagent, reason_json),
            ).fetchone():
                return
            self.db.execute(
                "INSERT INTO prompts (session_id, subagent, key, reason, since) VALUES (?, ?, ?, ?, ?)",
                (session_id, subagent, key, reason_json, iso(now)),
            )

    @locked
    def clear_prompts(self, session_id: int, *, key: str | None = None) -> None:
        """Resolve waiting prompts: the one for `key`, or all of them."""
        with self.db:
            if key is None:
                self.db.execute("DELETE FROM prompts WHERE session_id = ?", (session_id,))
            else:
                self.db.execute("DELETE FROM prompts WHERE session_id = ? AND key = ?", (session_id, key))

    @locked
    def clear_loose_prompts(self, session_id: int, subagent: str) -> None:
        """Backstop on later tool activity: drop this subagent's prompts that no open call holds.
        Elicitations wait inside a call of their own and clear on their result."""
        with self.db:
            self.db.execute(
                "DELETE FROM prompts WHERE session_id = ? AND subagent = ? AND (key IS NULL OR (key NOT LIKE 'elicitation:%'"
                " AND key NOT IN (SELECT tool_use_id FROM tool_uses WHERE session_id = ?)))",
                (session_id, subagent, session_id),
            )

    @locked
    def end_turn(self, session_id: int, subagent: str | None = None) -> None:
        """A turn ended (the main session's, or a subagent's; None = every one): its prompts and calls are over."""
        with self.db:
            for table in ("prompts", "tool_uses"):
                if subagent is None:
                    self.db.execute(f"DELETE FROM {table} WHERE session_id = ?", (session_id,))
                else:
                    self.db.execute(f"DELETE FROM {table} WHERE session_id = ? AND subagent = ?", (session_id, subagent))

    @locked
    def settle(self, session_id: int, now: datetime) -> None:
        """The shown state: Needs you for the oldest waiting prompt, else the base state; since = last change."""
        prompt = self.db.execute(
            "SELECT reason FROM prompts WHERE session_id = ? ORDER BY id LIMIT 1", (session_id,)
        ).fetchone()
        was = self.db.execute("SELECT state FROM sessions WHERE id = ?", (session_id,)).fetchone()["state"]
        with self.db:
            if prompt:
                self.db.execute(
                    "UPDATE sessions SET state_since = CASE WHEN state = 'Needs you' THEN state_since ELSE ? END,"
                    " transitions = transitions + (state != 'Needs you'),"
                    " state = 'Needs you', reason = ? WHERE id = ?",
                    (iso(now), prompt["reason"], session_id),
                )
            else:
                self.db.execute(
                    "UPDATE sessions SET state_since = CASE WHEN state = base THEN state_since ELSE ? END,"
                    " transitions = transitions + (state != base),"
                    " state = base, reason = base_reason WHERE id = ?",
                    (iso(now), session_id),
                )
            row = self.db.execute("SELECT state, reason FROM sessions WHERE id = ?", (session_id,)).fetchone()
            job = self.db.execute("SELECT id FROM jobs WHERE session_id = ? ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
            if job and was != "Needs you" and row["state"] == "Needs you":
                self._job_event(job["id"], now, "needs", f"Needs you: {reason_text(json.loads(row['reason'] or 'null'))}")

    # ---------- Sounds (rules in sounds.py) ----------

    @locked
    def schedule_sound(self, session_id: int, transition: int, sound: str, due: datetime) -> None:
        """One sound per transition: scheduling it again can only bring it forward, never repeat it."""
        with self.db:
            self.db.execute(
                "INSERT INTO sounds (session_id, transition, sound, due) VALUES (?, ?, ?, ?)"
                " ON CONFLICT (session_id, transition) DO UPDATE SET due = MIN(due, excluded.due) WHERE seq IS NULL",
                (session_id, transition, sound, iso(due)),
            )

    @locked
    def release_sounds(self, now: datetime) -> None:
        """Due sounds play if their session is still live, shown, and in the transition they were for; the rest are dropped."""
        with self.db:
            due = self.db.execute(
                "SELECT k.id, k.transition = s.transitions AND s.ended_at IS NULL AND NOT s.hidden AS still FROM sounds k"
                " JOIN sessions s ON s.id = k.session_id WHERE k.seq IS NULL AND k.due <= ? ORDER BY k.due, k.id",
                (iso(now),),
            ).fetchall()
            for row in due:
                if row["still"]:
                    self.db.execute(
                        "UPDATE sounds SET seq = (SELECT COALESCE(MAX(seq), 0) + 1 FROM sounds) WHERE id = ?", (row["id"],)
                    )
                else:
                    self.db.execute("DELETE FROM sounds WHERE id = ?", (row["id"],))
            self.db.execute(
                "DELETE FROM sounds WHERE seq IS NOT NULL AND seq <= (SELECT MAX(seq) FROM sounds) - ?", (KEEP_SOUNDS,)
            )

    @locked
    def sounds(self) -> list[dict]:
        """The latest sounds played, in play order; `id` only grows, so the dashboard plays each once."""
        rows = self.db.execute(
            "SELECT k.seq, k.session_id, s.machine, k.sound, k.due FROM sounds k JOIN sessions s ON s.id = k.session_id"
            " WHERE k.seq IS NOT NULL ORDER BY k.seq"
        ).fetchall()
        return [
            {"id": r["seq"], "session_id": str(r["session_id"]), "machine": r["machine"], "sound": r["sound"], "at": r["due"]}
            for r in rows
        ]

    # ---------- Tracking ----------

    @locked
    def track_repo(self, repo: str, machine: str, repo_path: str, now: datetime) -> None:
        """This Machine tracks the repo; tracking it again keeps the first install time."""
        with self.db:
            self.db.execute(
                "INSERT INTO tracking (repo, machine, repo_path, installed_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT (repo, machine) DO UPDATE SET repo_path = excluded.repo_path",
                (repo, machine, repo_path, iso(now)),
            )

    @locked
    def untrack_repo(self, repo: str, machine: str, now: datetime) -> None:
        """The Machine stops tracking the repo: its live sessions there end (and stay in history)."""
        with self.db:
            self.db.execute("DELETE FROM tracking WHERE repo = ? AND machine = ?", (repo, machine))
            self.db.execute(
                "UPDATE sessions SET ended_at = ? WHERE repo = ? AND machine = ? AND ended_at IS NULL",
                (iso(now), repo, machine),
            )

    @locked
    def tracked_repos(self) -> list[dict]:
        rows = self.db.execute("SELECT repo, machine FROM tracking ORDER BY repo, machine").fetchall()
        repos: dict[str, list[str]] = {}
        for r in rows:
            repos.setdefault(r["repo"], []).append(r["machine"])
        return [{"repo": repo, "machines": machines} for repo, machines in repos.items()]

    @locked
    def machine_seen(self, machine: str, now: datetime) -> None:
        """Any event, queued ones included, is the Machine reporting."""
        with self.db:
            self.db.execute(
                "INSERT INTO machines (machine, last_seen) VALUES (?, ?)"
                " ON CONFLICT (machine) DO UPDATE SET last_seen = excluded.last_seen",
                (machine, iso(now)),
            )

    @locked
    def machines(self) -> list[dict]:
        """Machines that track a repo or have a live session, each with its live session count.

        A Machine with no event recorded (tracked before the server recorded them) was last seen when it
        installed or its session last changed state.
        """
        rows = self.db.execute(
            "WITH active (machine, seen, live) AS ("
            "  SELECT machine, installed_at, 0 FROM tracking"
            "  UNION ALL SELECT machine, state_since, 1 FROM sessions WHERE ended_at IS NULL)"
            " SELECT a.machine, COALESCE(m.last_seen, MAX(a.seen)) AS last_seen, SUM(a.live) AS sessions"
            " FROM active a LEFT JOIN machines m USING (machine)"
            " GROUP BY a.machine ORDER BY a.machine"
        ).fetchall()
        return [dict(r) for r in rows]
    @locked
    def save_poll(self, repo: str, items: list[dict], pulls: list[dict]) -> None:
        """The repo's Work items and PRs as of the latest poll, replacing the previous poll's."""
        with self.db:
            self.db.execute("DELETE FROM work_items WHERE repo = ?", (repo,))
            self.db.executemany(
                "INSERT INTO work_items (repo, number, title, state, url, kind, parent, blocked_by, type, assignees, map)"
                " VALUES (:repo, :number, :title, :state, :url, :kind, :parent, :blocked_by, :type, :assignees, :map)",
                [{"parent": None, "type": None, **item, "repo": repo, "blocked_by": json.dumps(item.get("blocked_by", [])),
                  "assignees": json.dumps(item.get("assignees", [])),
                  "map": None if item.get("map") is None else json.dumps(item["map"])}
                 for item in items],
            )
            self.db.execute("DELETE FROM pull_requests WHERE repo = ?", (repo,))
            self.db.executemany(
                "INSERT INTO pull_requests (repo, number, title, state, draft, url, closes)"
                " VALUES (:repo, :number, :title, :state, :draft, :url, :closes)",
                [{**pull, "repo": repo, "closes": json.dumps(pull.get("closes", []))} for pull in pulls],
            )
            # A PR the poll found for a Job stays the Job's, so its closing or merging ends the Job.
            for job in self.db.execute("SELECT * FROM jobs WHERE repo = ? AND pr_url IS NULL ORDER BY id", (repo,)).fetchall():
                if pr := self._job_pr(job):
                    self.db.execute("UPDATE jobs SET pr_url = ? WHERE id = ?", (pr["url"], job["id"]))

    @locked
    def work_items(self) -> list[dict]:
        """Work items of repos some Machine still tracks."""
        rows = self.db.execute(
            "SELECT repo, number, title, state, url, kind FROM work_items"
            " WHERE repo IN (SELECT repo FROM tracking) ORDER BY repo, number"
        ).fetchall()
        return [dict(r) for r in rows]

    @locked
    def pull_requests(self) -> list[dict]:
        """PRs of repos some Machine still tracks."""
        rows = self.db.execute(
            "SELECT repo, number, title, state, draft, url FROM pull_requests"
            " WHERE repo IN (SELECT repo FROM tracking) ORDER BY repo, number"
        ).fetchall()
        return [{**dict(r), "draft": bool(r["draft"])} for r in rows]

    @locked
    def record_skill_start(self, session_id: int, skill: str, repo: str, number: int, typed: bool) -> None:
        """A skill started against a Work item. The Skill tool call that follows a typed `/skill` is the same start."""
        with self.db:
            if not typed:
                latest = self.db.execute(
                    "SELECT skill, repo, number FROM skill_starts WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                    (session_id,),
                ).fetchone()
                if latest and tuple(latest) == (skill, repo, number):
                    return
            self.db.execute(
                "INSERT INTO skill_starts (session_id, skill, repo, number) VALUES (?, ?, ?, ?)",
                (session_id, skill, repo, number),
            )

    @locked
    def live_skill_starts(self) -> list[dict]:
        """Skill starts in live sessions, with the Work item's kind (None until polled, or not a Work item)."""
        rows = self.db.execute(
            "SELECT k.session_id, k.skill, k.repo, k.number, w.kind, s.mattpocock_skills_version FROM skill_starts k"
            " JOIN sessions s ON s.id = k.session_id"
            " LEFT JOIN work_items w ON w.repo = k.repo AND w.number = k.number"
            " WHERE s.ended_at IS NULL ORDER BY k.id"
        ).fetchall()
        return [{**dict(r), "session_id": str(r["session_id"])} for r in rows]

    # ---------- Jobs ----------

    @locked
    def start_job(self, session_id: int, kind: str, repo: str, number: int | None, now: datetime) -> int:
        """A new Job in the session; older ones are never closed by it."""
        with self.db:
            job_id = self.db.execute(
                "INSERT INTO jobs (session_id, kind, repo, number, started_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, kind, repo, number, iso(now)),
            ).lastrowid
            self._flag_duplicate(job_id)
            self._job_event(job_id, now, "start", "Job started" + (f": #{number}" if number is not None else ""))
            return job_id

    def _job_event(self, job_id: int, now: datetime, kind: str, text: str, step_id: int | None = None,
                   phase: str | None = None) -> None:
        self.db.execute(
            "INSERT INTO job_events (job_id, at, kind, text, step_id, phase) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, iso(now), kind, text, step_id, phase),
        )

    def _flag_duplicate(self, job_id: int) -> None:
        """Flag the Job a duplicate of the earliest other active Job (any session, any Machine) on its Work item."""
        job = self.db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job["number"] is None or job["duplicate_of"] is not None:
            return
        for other in self.db.execute(
            "SELECT * FROM jobs WHERE repo = ? AND number = ? AND id != ? ORDER BY id", (job["repo"], job["number"], job_id)
        ).fetchall():
            if self._stage(other, self._job_pr(other)) not in ENDED:
                self.db.execute("UPDATE jobs SET duplicate_of = ? WHERE id = ?", (other["id"], job_id))
                return

    @locked
    def duplicate_of(self, job_id: int) -> int | None:
        return self.db.execute("SELECT duplicate_of FROM jobs WHERE id = ?", (job_id,)).fetchone()["duplicate_of"]

    @locked
    def current_job(self, session_id: int) -> int | None:
        """The session's most recently started Job."""
        row = self.db.execute("SELECT id FROM jobs WHERE session_id = ? ORDER BY id DESC LIMIT 1", (session_id,)).fetchone()
        return row["id"] if row else None

    @locked
    def job_session(self, job_id: int) -> int | None:
        row = self.db.execute("SELECT session_id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return row["session_id"] if row else None

    @locked
    def set_job_number(self, job_id: int, number: int) -> None:
        """The Job's Work item; a Step that didn't know its Ticket (a Ticket Job's one Step) works the same one."""
        with self.db:
            self.db.execute("UPDATE jobs SET number = ? WHERE id = ?", (number, job_id))
            self._flag_duplicate(job_id)
            self.db.execute("UPDATE steps SET number = ? WHERE job_id = ? AND number IS NULL", (number, job_id))

    @locked
    def job_kind(self, job_id: int) -> str | None:
        row = self.db.execute("SELECT kind FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return row["kind"] if row else None

    # ---------- Steps and Phases (rules in phases.py) ----------

    @locked
    def add_step(self, job_id: int, number: int | None, now: datetime, phase: str | None = None) -> int:
        """A Step of the Job, its Phase unknown unless given."""
        with self.db:
            return self.db.execute(
                "INSERT INTO steps (job_id, number, phase, first_phase, phase_since) VALUES (?, ?, ?, ?, ?)",
                (job_id, number, phase, phase, iso(now)),
            ).lastrowid

    @locked
    def spec_tickets(self, repo: str, spec: int) -> list[int]:
        """The Spec's child Tickets, as last polled."""
        rows = self.db.execute(
            "SELECT number FROM work_items WHERE repo = ? AND parent = ? AND kind = 'Ticket' ORDER BY number", (repo, spec)
        )
        return [r["number"] for r in rows]

    @locked
    def jobs_of_kind(self, repo: str, kind: str) -> list[int]:
        return [r["id"] for r in self.db.execute("SELECT id FROM jobs WHERE repo = ? AND kind = ? ORDER BY id", (repo, kind))]

    @locked
    def job_number(self, job_id: int) -> int | None:
        row = self.db.execute("SELECT number FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return row["number"] if row else None

    @locked
    def job_steps(self, job_id: int) -> list[int]:
        return [r["id"] for r in self.db.execute("SELECT id FROM steps WHERE job_id = ? ORDER BY id", (job_id,))]

    @locked
    def job_step_numbered(self, job_id: int, number: int) -> int | None:
        """The Job's Step for that Ticket."""
        row = self.db.execute("SELECT id FROM steps WHERE job_id = ? AND number = ? ORDER BY id LIMIT 1", (job_id, number)).fetchone()
        return row["id"] if row else None

    @locked
    def map_agent(self, job_id: int, agent_id: str, step_id: int) -> None:
        """The Job's subagent works this Step."""
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO step_agents VALUES (?, ?, ?)", (job_id, agent_id, step_id))

    @locked
    def agent_step(self, job_id: int, agent_id: str) -> int | None:
        row = self.db.execute("SELECT step_id FROM step_agents WHERE job_id = ? AND agent_id = ?", (job_id, agent_id)).fetchone()
        return row["step_id"] if row else None

    @locked
    def spec_step_ticket(self, step_id: int | None) -> int | None:
        """The Ticket a Spec Job's Step works, which what its subagent raises names; None for a Ticket Job's Step."""
        if step_id is None:
            return None
        row = self.db.execute(
            "SELECT s.number FROM steps s JOIN jobs j ON j.id = s.job_id WHERE s.id = ? AND j.kind = ?", (step_id, SPEC_JOB)
        ).fetchone()
        return row["number"] if row else None

    @locked
    def step_phase(self, step_id: int) -> str | None:
        row = self.db.execute("SELECT phase FROM steps WHERE id = ?", (step_id,)).fetchone()
        return row["phase"] if row else None

    @locked
    def set_phase(self, step_id: int, phase: str | None, now: datetime) -> None:
        """The Step's Phase; a change joins its Job's replay and its Phase track."""
        with self.db:
            step = self.db.execute("SELECT job_id, number, phase FROM steps WHERE id = ?", (step_id,)).fetchone()
            if step and step["phase"] != phase:
                ticket = f"#{step['number']} " if step["number"] is not None else ""
                text = phase if phase is not None else "started: Phase unknown"
                self._job_event(step["job_id"], now, "phase", f"{ticket}{text}", step_id, phase)
            self.db.execute(
                "UPDATE steps SET phase_since = CASE WHEN phase IS ? THEN phase_since ELSE ? END, phase = ? WHERE id = ?",
                (phase, iso(now), phase, step_id),
            )

    @locked
    def steps(self) -> list[dict]:
        """Steps of Jobs in repos some Machine tracks, oldest first, each with its Ticket's title once polled."""
        rows = self.db.execute(
            "SELECT s.id, s.job_id, j.session_id, j.repo, s.number, w.title, s.phase, s.phase_since, w.blocked_by"
            " FROM steps s JOIN jobs j ON j.id = s.job_id"
            " LEFT JOIN work_items w ON w.repo = j.repo AND w.number = s.number"
            " WHERE j.repo IN (SELECT repo FROM tracking) ORDER BY s.id"
        ).fetchall()
        return [
            {**dict(r), "id": str(r["id"]), "job_id": str(r["job_id"]), "session_id": str(r["session_id"]),
             "blocked_by": json.loads(r["blocked_by"] or "[]")}
            for r in rows
        ]

    @locked
    def merged_jobs(self, repo: str) -> list[int]:
        """Jobs in the repo whose PR has merged."""
        rows = self.db.execute("SELECT * FROM jobs WHERE repo = ?", (repo,)).fetchall()
        merged = []
        for job in rows:
            pr = self._job_pr(job)
            if pr and self.db.execute(
                "SELECT 1 FROM pull_requests WHERE repo = ? AND url = ? AND state = 'merged'", (repo, pr["url"])
            ).fetchone():
                merged.append(job["id"])
        return merged

    @locked
    def set_job_worktree(self, job_id: int, worktree: str, branch: str | None = None) -> None:
        """Where the Job works; a known branch is kept until another is learnt for the same worktree."""
        with self.db:
            self.db.execute(
                "UPDATE jobs SET branch = CASE WHEN worktree IS ? THEN COALESCE(?, branch) ELSE ? END, worktree = ?"
                " WHERE id = ?",
                (worktree, branch, branch, worktree, job_id),
            )

    @locked
    def job_tree(self, job_id: int) -> tuple[str | None, str | None]:
        """Where the Job works: its worktree and branch, each None while unknown."""
        row = self.db.execute("SELECT worktree, branch FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return (row["worktree"], row["branch"]) if row else (None, None)

    @locked
    def set_job_pr(self, job_id: int, url: str) -> None:
        with self.db:
            self.db.execute("UPDATE jobs SET pr_url = ? WHERE id = ?", (url, job_id))

    @locked
    def work_item(self, repo: str, number: int) -> dict | None:
        row = self.db.execute("SELECT title, url FROM work_items WHERE repo = ? AND number = ?", (repo, number)).fetchone()
        return dict(row) if row else None

    def _job_pr(self, job: sqlite3.Row) -> dict | None:
        """The Job's PR: the one it reported (as the poll knows it, if it does), else an open or merged PR
        closing its Work item or one of its Steps' Tickets (a Spec Job's PR may close only the Tickets) that no
        other Job has, unless the Job is a duplicate of one still going. A reported
        PR the poll hasn't seen yet counts as non-draft, as the Job was told."""
        pulls = self.db.execute(
            "SELECT number, url, draft, state, closes FROM pull_requests WHERE repo = ? ORDER BY number DESC", (job["repo"],)
        ).fetchall()
        found = next((p for p in pulls if p["url"] == job["pr_url"]), None)
        if found is None and job["pr_url"] is None and job["number"] is not None and not self._original_active(job):
            items = {job["number"]} | {
                r["number"] for r in self.db.execute("SELECT number FROM steps WHERE job_id = ? AND number IS NOT NULL", (job["id"],))
            }
            claimed = {r["pr_url"] for r in self.db.execute(
                "SELECT pr_url FROM jobs WHERE repo = ? AND id != ? AND pr_url IS NOT NULL", (job["repo"], job["id"]))}
            found = next((p for p in pulls if p["state"] != "closed" and p["url"] not in claimed
                          and items & set(json.loads(p["closes"]))), None)
        if found is not None:
            return {"number": found["number"], "url": found["url"], "draft": bool(found["draft"]), "state": found["state"]}
        if job["pr_url"]:
            m = re.search(r"/pull/(\d+)", job["pr_url"])
            return {"number": int(m[1]) if m else None, "url": job["pr_url"], "draft": False, "state": "open"}
        return None

    def _pr_checks(self, repo: str, pr: dict | None) -> list[dict] | None:
        """The CI checks on the PR's head, as last read; None until read."""
        row = pr and self.db.execute(
            "SELECT checks FROM pr_checks WHERE repo = ? AND number = ?", (repo, pr["number"])).fetchone()
        return json.loads(row["checks"]) if row else None

    def _original_active(self, job: sqlite3.Row) -> bool:
        """Whether the Job is a duplicate whose original is still going: a PR closing their Work item is the original's."""
        if job["duplicate_of"] is None:
            return False
        original = self.db.execute("SELECT * FROM jobs WHERE id = ?", (job["duplicate_of"],)).fetchone()
        return original is not None and self._stage(original, self._job_pr(original)) not in ENDED

    @locked
    def abandon_job(self, job_id: int, now: datetime) -> bool:
        """The human abandoned the Job; false when there is no such Job."""
        with self.db:
            return self.db.execute(
                "UPDATE jobs SET abandoned_at = COALESCE(abandoned_at, ?) WHERE id = ?", (iso(now), job_id)
            ).rowcount > 0

    def _stage(self, job: sqlite3.Row, pr: dict | None) -> str:
        item = self.db.execute(
            "SELECT state FROM work_items WHERE repo = ? AND number = ?", (job["repo"], job["number"])
        ).fetchone()
        return stage_of(pr, job["abandoned_at"] is not None, item and item["state"])

    @locked
    def job_stage(self, job_id: int) -> str:
        """In progress until a non-draft PR exists (which makes it Done), then PR open, Merged, Closed or Abandoned."""
        job = self.db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._stage(job, self._job_pr(job))

    @locked
    def jobs(self) -> list[dict]:
        """Jobs in repos some Machine tracks, oldest first, with their Machine, Work item, PR, stage and (once over) end."""
        rows = self.db.execute(
            "SELECT j.*, w.title, w.url, s.machine FROM jobs j JOIN sessions s ON s.id = j.session_id"
            " LEFT JOIN work_items w ON w.repo = j.repo AND w.number = j.number WHERE j.repo IN (SELECT repo FROM tracking) ORDER BY j.id"
        ).fetchall()
        out = []
        for j in rows:
            pr = self._job_pr(j)
            out.append({
                "id": str(j["id"]), "session_id": str(j["session_id"]), "machine": j["machine"], "kind": j["kind"], "repo": j["repo"],
                "number": j["number"],
                "work_item": {"title": j["title"], "url": j["url"]} if j["title"] is not None else None,
                "worktree": j["worktree"], "branch": j["branch"],
                "stage": self._stage(j, pr),
                "pr": pr and {k: pr[k] for k in ("number", "url", "draft")}, "started_at": j["started_at"], "ended_at": j["ended_at"],
                "pr_checks": self._pr_checks(j["repo"], pr),
                "pr_track": [{"stage": t["stage"], "at": t["at"]} for t in json.loads(j["pr_track"]) if pr and t["url"] == pr["url"]],
                "duplicate_of": None if j["duplicate_of"] is None else str(j["duplicate_of"]),
            })
        return out

    # ---------- Wayfinder sessions (rules in wayfinder.py) ----------

    @locked
    def set_wayfinder(self, session_id: int, **fields: int | list[str] | None) -> None:
        """Set the session's `map`, `ticket` or `questions`."""
        with self.db:
            self.db.execute("INSERT INTO wayfinder (session_id) VALUES (?) ON CONFLICT DO NOTHING", (session_id,))
            for name, value in fields.items():
                assert name in ("map", "ticket", "questions")
                stored = json.dumps(value) if name == "questions" else value
                self.db.execute(f"UPDATE wayfinder SET {name} = ? WHERE session_id = ?", (stored, session_id))

    @locked
    def wayfinder(self, session_id: int) -> dict:
        row = self.db.execute("SELECT * FROM wayfinder WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            return {"map": None, "ticket": None, "questions": []}
        return {"map": row["map"], "ticket": row["ticket"], "questions": json.loads(row["questions"])}

    @locked
    def record_decision_ticket(self, session_id: int, number: int, action: str) -> None:
        """The session `created` or `closed` the ticket."""
        with self.db:
            self.db.execute("INSERT INTO decision_tickets (session_id, number, action) VALUES (?, ?, ?)"
                            " ON CONFLICT DO NOTHING", (session_id, number, action))

    @locked
    def decision_tickets(self, session_id: int, action: str) -> list[int]:
        return [r["number"] for r in self.db.execute(
            "SELECT number FROM decision_tickets WHERE session_id = ? AND action = ? ORDER BY id", (session_id, action))]

    @locked
    def wayfinder_sessions(self, kind: str) -> list[dict]:
        """Each live session of that kind, with its Map, Decision ticket, question titles and the tickets it created
        and closed."""
        rows = self.db.execute("SELECT id FROM sessions WHERE ended_at IS NULL AND kind = ? ORDER BY id", (kind,))
        return [{"session_id": str(r["id"]), **self.wayfinder(r["id"]),
                 "created": self.decision_tickets(r["id"], "created"), "closed": self.decision_tickets(r["id"], "closed")}
                for r in rows.fetchall()]

    # ---------- research, to-spec and to-tickets sessions (rules in planning.py) ----------

    @locked
    def plan(self, session_id: int, kind: str) -> dict | None:
        row = self.db.execute("SELECT facts FROM plans WHERE session_id = ? AND kind = ?", (session_id, kind)).fetchone()
        return None if row is None else json.loads(row["facts"])

    @locked
    def set_plan(self, session_id: int, kind: str, facts: dict) -> None:
        with self.db:
            self.db.execute("INSERT INTO plans (session_id, kind, facts) VALUES (?, ?, ?)"
                            " ON CONFLICT DO UPDATE SET facts = excluded.facts", (session_id, kind, json.dumps(facts)))

    @locked
    def plan_sessions(self, kind: str) -> list[dict]:
        """Each live session of that kind, with its repo and its facts as that kind."""
        rows = self.db.execute(
            "SELECT s.id, s.repo, p.facts FROM sessions s JOIN plans p ON p.session_id = s.id AND p.kind = s.kind"
            " WHERE s.ended_at IS NULL AND s.kind = ? ORDER BY s.id", (kind,)).fetchall()
        return [{"session_id": str(r["id"]), "repo": r["repo"], **json.loads(r["facts"])} for r in rows]

    @locked
    def issue(self, repo: str, number: int) -> dict | None:
        """A Work item as last polled, with its type, claim and parent."""
        row = self.db.execute("SELECT * FROM work_items WHERE repo = ? AND number = ?", (repo, number)).fetchone()
        if row is None:
            return None
        return {"number": row["number"], "title": row["title"], "state": row["state"], "url": row["url"],
                "kind": row["kind"], "parent": row["parent"], "type": row["type"],
                "assignees": json.loads(row["assignees"] or "[]"), "blocked_by": json.loads(row["blocked_by"] or "[]")}

    @locked
    def maps(self) -> list[dict]:
        """Maps of repos some Machine still tracks, each with its body's facts and its Decision tickets."""
        maps = self.db.execute(
            "SELECT * FROM work_items WHERE kind = 'Map' AND repo IN (SELECT repo FROM tracking) ORDER BY repo, number"
        ).fetchall()
        out = []
        for m in maps:
            children = self.db.execute(
                "SELECT number FROM work_items WHERE repo = ? AND parent = ? AND kind = 'Decision ticket' ORDER BY number",
                (m["repo"], m["number"]),
            ).fetchall()
            body = json.loads(m["map"] or "{}")
            gists, out_of_scope = body.get("gists", {}), set(body.get("out_of_scope", []))
            # Out of scope is not drawn; a closed ticket has the gist the Map records for it.
            tickets = [{**t, "mode": mode_of(t["type"]), "gist": gists.get(str(t["number"]))}
                       for c in children if c["number"] not in out_of_scope and (t := self.issue(m["repo"], c["number"]))]
            out.append({"repo": m["repo"], "number": m["number"], "title": m["title"], "url": m["url"], "state": m["state"],
                        "destination": body.get("destination"), "fog": body.get("fog", []), "tickets": tickets})
        return out

    @locked
    def chronicle_job(self, job_id: int, now: datetime) -> None:
        """Its non-draft PR, the first time it is known, and its end, the first time it is seen, join the Job's replay."""
        with self.db:
            job = self.db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            pr = self._job_pr(job)
            if pr and not pr["draft"] and not self.db.execute(
                "SELECT 1 FROM job_events WHERE job_id = ? AND kind = 'pr' AND text = ?", (job_id, f"PR: {pr['url']}")
            ).fetchone():
                self._job_event(job_id, now, "pr", f"PR: {pr['url']}")
            if pr:
                track = json.loads(job["pr_track"])
                seen = [t["stage"] for t in track if t["url"] == pr["url"]]
                if not seen or seen[-1] != pr_stage(pr):
                    track.append({"url": pr["url"], "stage": pr_stage(pr), "at": iso(now)})
                    self.db.execute("UPDATE jobs SET pr_track = ? WHERE id = ?", (json.dumps(track), job_id))
            stage = self._stage(job, pr)
            if stage in ENDED and job["ended_at"] is None:
                self.db.execute("UPDATE jobs SET ended_at = ? WHERE id = ?", (iso(now), job_id))
                self._job_event(job_id, now, "end", stage)

    @locked
    def repo_jobs(self, repo: str) -> list[int]:
        return [r["id"] for r in self.db.execute("SELECT id FROM jobs WHERE repo = ? ORDER BY id", (repo,))]

    @locked
    def record_job_event(self, job_id: int, now: datetime, kind: str, text: str) -> None:
        with self.db:
            self._job_event(job_id, now, kind, text)

    @locked
    def job_replay(self, job_id: int) -> dict | None:
        """The Job's timeline for its History replay: its Steps and every event, oldest first; None if no such Job."""
        job = self.db.execute("SELECT started_at, ended_at FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            return None
        start = datetime.fromisoformat(job["started_at"])
        steps = self.db.execute(
            "SELECT s.id, s.number, w.title, s.first_phase FROM steps s JOIN jobs j ON j.id = s.job_id"
            " LEFT JOIN work_items w ON w.repo = j.repo AND w.number = s.number WHERE s.job_id = ? ORDER BY s.id",
            (job_id,),
        ).fetchall()
        rows = self.db.execute("SELECT * FROM job_events WHERE job_id = ? ORDER BY id", (job_id,)).fetchall()
        return {
            "job_id": str(job_id),
            "started_at": job["started_at"],
            "ended_at": job["ended_at"],
            "steps": [
                {"id": str(s["id"]), "number": s["number"], "title": s["title"], "phase": s["first_phase"]} for s in steps
            ],
            "events": [
                {
                    "t": round((datetime.fromisoformat(e["at"]) - start).total_seconds()), "at": e["at"],
                    "kind": e["kind"], "text": e["text"],
                    "step_id": None if e["step_id"] is None else str(e["step_id"]), "phase": e["phase"],
                }
                for e in rows
            ],
        }

    # ---------- Step detail ----------

    @locked
    def record_test_run(self, step_id: int, result: str, passed: int | None, failed: int | None, now: datetime) -> None:
        """A test run; a passing one ends any churn."""
        with self.db:
            self.db.execute(
                "INSERT INTO test_runs (step_id, at, result, passed, failed) VALUES (?, ?, ?, ?, ?)",
                (step_id, iso(now), result, passed, failed),
            )
            if result == "pass":
                self.db.execute("UPDATE step_files SET since_pass = 0 WHERE step_id = ?", (step_id,))

    @locked
    def prs_to_check(self, repo: str) -> list[int]:
        """The open PRs of the repo's Jobs still going, whose CI checks the poll reads."""
        numbers = []
        for job in self.db.execute("SELECT * FROM jobs WHERE repo = ? ORDER BY id", (repo,)).fetchall():
            pr = self._job_pr(job)
            if pr and pr["number"] and pr["state"] == "open" and self._stage(job, pr) not in ENDED:
                numbers.append(pr["number"])
        return list(dict.fromkeys(numbers))

    @locked
    def save_checks(self, repo: str, number: int, checks: list[dict]) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO pr_checks VALUES (?, ?, ?)", (repo, number, json.dumps(checks)))

    @locked
    def start_review(self, job_id: int) -> None:
        with self.db:
            self.db.execute("UPDATE jobs SET reviewed = 1 WHERE id = ?", (job_id,))

    @locked
    def review_started(self, job_id: int) -> bool:
        row = self.db.execute("SELECT reviewed FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return bool(row and row["reviewed"])

    @locked
    def record_review(self, job_id: int, step_id: int | None, standards: int, spec: int, source: str) -> None:
        """The latest findings count; one read from a summary never replaces the agent's own report."""
        with self.db:
            self.db.execute(
                "INSERT INTO reviews VALUES (?, ?, ?, ?, ?) ON CONFLICT (job_id, step_id) DO UPDATE SET"
                " standards = excluded.standards, spec = excluded.spec, source = excluded.source"
                " WHERE excluded.source = 'report' OR reviews.source != 'report'",
                (job_id, step_id or 0, standards, spec, source),
            )

    @locked
    def job_reviews(self) -> dict[str, dict]:
        """Findings counts for a whole Job (a Spec Job's review of its integration branch), by Job id."""
        rows = self.db.execute(
            "SELECT r.* FROM reviews r JOIN jobs j ON j.id = r.job_id"
            " WHERE r.step_id = 0 AND j.repo IN (SELECT repo FROM tracking) ORDER BY r.job_id"
        )
        return {str(r["job_id"]): {k: r[k] for k in ("standards", "spec", "source")} for r in rows}

    @locked
    def step_active(self, step_id: int, now: datetime) -> None:
        with self.db:
            self.db.execute("UPDATE steps SET active_at = ? WHERE id = ?", (iso(now), step_id))

    @locked
    def checklist(self, step_id: int) -> list[dict] | None:
        row = self.db.execute("SELECT checklist FROM steps WHERE id = ?", (step_id,)).fetchone()
        return json.loads(row["checklist"]) if row and row["checklist"] else None

    @locked
    def set_checklist(self, step_id: int, items: list[dict]) -> None:
        with self.db:
            self.db.execute("UPDATE steps SET checklist = ? WHERE id = ?", (json.dumps(items), step_id))

    @locked
    def record_commit(self, step_id: int, commit: dict, now: datetime) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO step_commits (step_id, at, sha, message, files, added, deleted)"
                " VALUES (:step_id, :at, :sha, :message, :files, :added, :deleted)",
                {**commit, "step_id": step_id, "at": iso(now)},
            )

    @locked
    def record_merge(self, step_id: int, sha: str | None, now: datetime) -> None:
        """A Spec Job's Step merged into its integration branch: the first merge's time, the latest known SHA."""
        with self.db:
            self.db.execute(
                "UPDATE steps SET merged_at = COALESCE(merged_at, ?), merged_sha = COALESCE(?, merged_sha) WHERE id = ?",
                (iso(now), sha, step_id),
            )

    @locked
    def record_edit(self, step_id: int, path: str, lines: tuple[int, int] | None) -> None:
        """One edit to a file, with the (added, deleted) lines of its patch; None (unknown) makes the file's unknown."""
        added, deleted = lines or (None, None)
        with self.db:
            self.db.execute(
                "INSERT INTO step_files (step_id, path, edits, since_pass, added, deleted) VALUES (?, ?, 1, 1, ?, ?)"
                " ON CONFLICT (step_id, path) DO UPDATE SET edits = edits + 1, since_pass = since_pass + 1,"
                " added = added + excluded.added, deleted = deleted + excluded.deleted",
                (step_id, path, added, deleted),
            )

    @locked
    def step_details(self, now: datetime, working: set[str]) -> dict[str, dict]:
        """What each Step (of a Job in a repo some Machine tracks) has done, by Step id, and whether it is
        struggling; `working` holds the ids of the sessions Working (Stale included), whose Steps can be silent."""
        rows = self.db.execute(
            "SELECT j.*, s.id AS step_id, s.checklist, s.phase, s.merged_at, s.merged_sha, s.first_phase, COALESCE(s.active_at, s.phase_since) AS active_at"
            " FROM steps s JOIN jobs j ON j.id = s.job_id WHERE j.repo IN (SELECT repo FROM tracking) ORDER BY s.id"
        ).fetchall()
        ids = [r["step_id"] for r in rows]
        details: dict[str, dict] = {str(i): {"phase_events": [], "tests": None, "files": [], "commits": [], "pr": None,
                                    "review": None, "checklist": None, "merge": None} for i in ids}
        # The Phase track: each Step's Phase changes from its replay, each from the Phase before (first the one it began in).
        phase = {str(r["step_id"]): r["first_phase"] for r in rows}
        for e in self.db.execute("SELECT step_id, at, phase FROM job_events WHERE kind = 'phase' AND step_id IS NOT NULL ORDER BY id"):
            if (d := details.get(str(e["step_id"]))) is not None:
                d["phase_events"].append({"at": e["at"], "from": phase[str(e["step_id"])], "to": e["phase"]})
                phase[str(e["step_id"])] = e["phase"]
        for f in self.db.execute("SELECT step_id, path, edits, added, deleted FROM step_files ORDER BY id"):
            if (d := details.get(str(f["step_id"]))) is not None:
                d["files"].append({k: f[k] for k in ("path", "edits", "added", "deleted")})
        for c in self.db.execute("SELECT * FROM step_commits ORDER BY id"):
            if (d := details.get(str(c["step_id"]))) is not None:
                d["commits"].append({k: c[k] for k in ("sha", "message", "files", "added", "deleted")})
        for r in rows:
            if r["merged_at"]:
                details[str(r["step_id"])]["merge"] = {"sha": r["merged_sha"], "at": r["merged_at"]}
            if r["checklist"]:
                details[str(r["step_id"])]["checklist"] = [
                    {"text": i["text"], "status": i["status"]} for i in json.loads(r["checklist"])]
            # A Ticket Job's Step ends as the Job's PR; a Spec Job's Steps merge into its integration branch.
            if r["kind"] == "Ticket Job" and (pr := self._job_pr(r)):
                details[str(r["step_id"])]["pr"] = {**{k: pr[k] for k in ("number", "url", "draft")},
                                            "checks": self._pr_checks(r["repo"], pr)}
        for v in self.db.execute("SELECT * FROM reviews WHERE step_id != 0"):
            if (d := details.get(str(v["step_id"]))) is not None:
                d["review"] = {k: v[k] for k in ("standards", "spec", "source")}
        runs: dict[str, list[dict]] = {}
        for r in self.db.execute("SELECT step_id, at, result, passed, failed FROM test_runs ORDER BY id"):
            runs.setdefault(str(r["step_id"]), []).append({k: r[k] for k in ("at", "result", "passed", "failed")})
        for step_id, step_runs in runs.items():
            if (d := details.get(step_id)) is not None:
                last = step_runs[-1]
                d["tests"] = {"last": last["result"], "passed": last["passed"], "failed": last["failed"],
                              "runs": step_runs[-KEEP_RUNS:]}
        for r in rows:
            d = details[str(r["step_id"])]
            churned = [f["path"] for f in self.db.execute(
                "SELECT path FROM step_files WHERE step_id = ? AND since_pass >= ? ORDER BY id", (r["step_id"], CHURN_EDITS))]
            going = (str(r["session_id"]) in working and r["phase"] not in ("Pending", "Merged")
                     and self._stage(r, self._job_pr(r)) not in ENDED)
            silent_for = int((now - datetime.fromisoformat(r["active_at"])).total_seconds()) if going else None
            d["struggle"] = struggle_of([t["result"] for t in runs.get(str(r["step_id"]), [])], churned, silent_for)
        return details
