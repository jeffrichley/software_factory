"""SQLite state: stdlib sqlite3, no ORM."""

import functools
import json
import re
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .jobs import ENDED, stage_of
from .skills import AD_HOC

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
-- The Step each subagent of a Spec Job works, by the subagent's agent_id.
CREATE TABLE IF NOT EXISTS step_agents (
  job_id INTEGER NOT NULL REFERENCES jobs (id),
  agent_id TEXT NOT NULL,
  step_id INTEGER NOT NULL REFERENCES steps (id),
  PRIMARY KEY (job_id, agent_id)
);
-- A sound for one transition of a session's state, due at `due`. It plays (gets `seq`, the order the
-- dashboard plays sounds in) once due if the session is still in that transition, else it is dropped.
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
    "mattpocock_skills_version": "TEXT",
    "base": "TEXT NOT NULL DEFAULT 'Working'",  # the state shown when no prompt is waiting
    "base_reason": "TEXT",
    "reason": "TEXT",  # JSON reason shown with Needs you
    "seen": "INTEGER NOT NULL DEFAULT 0",  # Done has been seen by the human
    "hidden": "INTEGER NOT NULL DEFAULT 0",  # hidden by the human: out of the dashboard's views, and silent
    "transitions": "INTEGER NOT NULL DEFAULT 0",  # counts changes of shown state: a sound belongs to one
}
WORK_ITEM_COLUMNS = {
    "parent": "INTEGER",  # the parent issue's number: a Ticket's Spec, a Decision ticket's Map
    "blocked_by": "TEXT NOT NULL DEFAULT '[]'",  # JSON list of the issues in this repo that block it
}
JOB_COLUMNS = {
    "abandoned_at": "TEXT",  # when the human abandoned the Job on the dashboard
    "duplicate_of": "INTEGER",  # the active Job already on its Work item when it started (or learnt it): flagged, not blocked
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
        self.db.executescript(SCHEMA)
        with self.db:
            for table, columns in (("sessions", SESSION_COLUMNS), ("work_items", WORK_ITEM_COLUMNS),
                                   ("pull_requests", PULL_REQUEST_COLUMNS), ("jobs", JOB_COLUMNS)):
                have = {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}
                for column, decl in columns.items():
                    if column not in have:
                        self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    @locked
    def touch_session(self, machine: str, repo: str, cc_session_id: str, now: datetime) -> int:
        """The server's id for a Claude Code session, creating its row (Working) on first sight."""
        with self.db:
            self.db.execute(
                "INSERT INTO sessions (machine, repo, cc_session_id, state, state_since) VALUES (?, ?, ?, 'Working', ?)"
                " ON CONFLICT (machine, cc_session_id) DO NOTHING",
                (machine, repo, cc_session_id, iso(now)),
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
    def record_action(self, session_id: int, text: str, now: datetime) -> None:
        """The session's headline is now `text`; it joins the timeline, which keeps the last few."""
        with self.db:
            self.db.execute("UPDATE sessions SET headline = ? WHERE id = ?", (text, session_id))
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
            "SELECT id, machine, repo, cc_session_id, state, state_since, reason, seen, hidden, kind, skill, headline,"
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
                "state": r["state"], "state_since": r["state_since"],
                "reason": r["reason"] and json.loads(r["reason"]), "seen": bool(r["seen"]), "hidden": bool(r["hidden"]),
                "kind": r["kind"], "skill": r["skill"], "unknown_skill": r["unknown_skill"], "now": r["headline"],
                "actions": actions.get(r["id"], []),
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
                "INSERT INTO work_items (repo, number, title, state, url, kind, parent, blocked_by)"
                " VALUES (:repo, :number, :title, :state, :url, :kind, :parent, :blocked_by)",
                [{"parent": None, **item, "repo": repo, "blocked_by": json.dumps(item.get("blocked_by", []))}
                 for item in items],
            )
            self.db.execute("DELETE FROM pull_requests WHERE repo = ?", (repo,))
            self.db.executemany(
                "INSERT INTO pull_requests (repo, number, title, state, draft, url, closes)"
                " VALUES (:repo, :number, :title, :state, :draft, :url, :closes)",
                [{**pull, "repo": repo, "closes": json.dumps(pull.get("closes", []))} for pull in pulls],
            )
            # A PR the poll found for a Job stays the Job's, so its closing or merging ends the Job.
            for job in self.db.execute("SELECT * FROM jobs WHERE repo = ? AND pr_url IS NULL", (repo,)).fetchall():
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
            return job_id

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
                "INSERT INTO steps (job_id, number, phase, phase_since) VALUES (?, ?, ?, ?)",
                (job_id, number, phase, iso(now)),
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
    def step_number(self, step_id: int) -> int | None:
        row = self.db.execute("SELECT number FROM steps WHERE id = ?", (step_id,)).fetchone()
        return row["number"] if row else None

    @locked
    def step_phase(self, step_id: int) -> str | None:
        row = self.db.execute("SELECT phase FROM steps WHERE id = ?", (step_id,)).fetchone()
        return row["phase"] if row else None

    @locked
    def set_phase(self, step_id: int, phase: str, now: datetime) -> None:
        with self.db:
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
    def set_job_pr(self, job_id: int, url: str) -> None:
        with self.db:
            self.db.execute("UPDATE jobs SET pr_url = ? WHERE id = ?", (url, job_id))

    @locked
    def work_item(self, repo: str, number: int) -> dict | None:
        row = self.db.execute("SELECT title, url FROM work_items WHERE repo = ? AND number = ?", (repo, number)).fetchone()
        return dict(row) if row else None

    def _job_pr(self, job: sqlite3.Row) -> dict | None:
        """The Job's PR: the one it reported (as the poll knows it, if it does), else an open or merged PR
        closing its Work item or one of its Steps' Tickets (a Spec Job's PR may close only the Tickets). A reported
        PR the poll hasn't seen yet counts as non-draft, as the Job was told."""
        pulls = self.db.execute(
            "SELECT number, url, draft, state, closes FROM pull_requests WHERE repo = ? ORDER BY number DESC", (job["repo"],)
        ).fetchall()
        found = next((p for p in pulls if p["url"] == job["pr_url"]), None)
        if found is None and job["pr_url"] is None and job["number"] is not None:
            items = {job["number"]} | {
                r["number"] for r in self.db.execute("SELECT number FROM steps WHERE job_id = ? AND number IS NOT NULL", (job["id"],))
            }
            found = next((p for p in pulls if p["state"] != "closed" and items & set(json.loads(p["closes"]))), None)
        if found is not None:
            return {"number": found["number"], "url": found["url"], "draft": bool(found["draft"]), "state": found["state"]}
        if job["pr_url"]:
            m = re.search(r"/pull/(\d+)", job["pr_url"])
            return {"number": int(m[1]) if m else None, "url": job["pr_url"], "draft": False, "state": "open"}
        return None

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
        """Jobs in repos some Machine tracks, oldest first, with their Work item, PR and stage."""
        rows = self.db.execute(
            "SELECT j.*, w.title, w.url FROM jobs j LEFT JOIN work_items w ON w.repo = j.repo AND w.number = j.number"
            " WHERE j.repo IN (SELECT repo FROM tracking) ORDER BY j.id"
        ).fetchall()
        out = []
        for j in rows:
            pr = self._job_pr(j)
            out.append({
                "id": str(j["id"]), "session_id": str(j["session_id"]), "kind": j["kind"], "repo": j["repo"],
                "number": j["number"],
                "work_item": {"title": j["title"], "url": j["url"]} if j["title"] is not None else None,
                "worktree": j["worktree"], "branch": j["branch"],
                "stage": self._stage(j, pr),
                "pr": pr and {k: pr[k] for k in ("number", "url", "draft")}, "started_at": j["started_at"],
                "duplicate_of": None if j["duplicate_of"] is None else str(j["duplicate_of"]),
            })
        return out
