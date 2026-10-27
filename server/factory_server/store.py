"""SQLite state: stdlib sqlite3, no ORM."""

import functools
import json
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

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
    "transitions": "INTEGER NOT NULL DEFAULT 0",  # counts changes of shown state: a sound belongs to one
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
        have = {r["name"] for r in self.db.execute("PRAGMA table_info(sessions)")}
        with self.db:
            for column, decl in SESSION_COLUMNS.items():
                if column not in have:
                    self.db.execute(f"ALTER TABLE sessions ADD COLUMN {column} {decl}")

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
            "SELECT id, machine, repo, cc_session_id, state, state_since, reason, seen, kind, skill, headline,"
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
                "reason": r["reason"] and json.loads(r["reason"]), "seen": bool(r["seen"]),
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
        """Due sounds play if their session is still live in the transition they were for; the rest are dropped."""
        with self.db:
            due = self.db.execute(
                "SELECT k.id, k.transition = s.transitions AND s.ended_at IS NULL AS still FROM sounds k"
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
                "INSERT INTO work_items (repo, number, title, state, url, kind)"
                " VALUES (:repo, :number, :title, :state, :url, :kind)",
                [{**item, "repo": repo} for item in items],
            )
            self.db.execute("DELETE FROM pull_requests WHERE repo = ?", (repo,))
            self.db.executemany(
                "INSERT INTO pull_requests (repo, number, title, state, draft, url)"
                " VALUES (:repo, :number, :title, :state, :draft, :url)",
                [{**pull, "repo": repo} for pull in pulls],
            )

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
