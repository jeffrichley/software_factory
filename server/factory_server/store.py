"""SQLite state: stdlib sqlite3, no ORM."""

import functools
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
"""
# Columns added after the first release, so an existing database gains them on start.
SESSION_COLUMNS = {
    "kind": f"TEXT NOT NULL DEFAULT '{AD_HOC}'",
    "skill": "TEXT",
    "headline": "TEXT",
    "mattpocock_skills_version": "TEXT",
}
# The ad hoc detail view's timeline shows a session's last few actions; older ones are dropped.
KEEP_ACTIONS = 8


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
            self.db.execute(
                "UPDATE sessions SET ended_at = NULL, state = 'Working', state_since = ? WHERE id = ? AND ended_at IS NOT NULL",
                (iso(now), session_id),
            )

    @locked
    def end_session(self, session_id: int, now: datetime) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL", (iso(now), session_id))

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
        rows = self.db.execute(
            "SELECT id, machine, repo, state, state_since, kind, skill, headline,"
            " (SELECT skill FROM unknown_skills u WHERE u.session_id = sessions.id ORDER BY u.id DESC LIMIT 1) AS unknown_skill"
            " FROM sessions WHERE ended_at IS NULL ORDER BY id"
        ).fetchall()
        actions: dict[int, list[dict]] = {}
        for a in self.db.execute(
            "SELECT session_id, at, text FROM actions WHERE session_id IN"
            " (SELECT id FROM sessions WHERE ended_at IS NULL) ORDER BY id"
        ):
            actions.setdefault(a["session_id"], []).append({"at": a["at"], "text": a["text"]})
        return [
            {
                "id": str(r["id"]), "machine": r["machine"], "repo": r["repo"], "state": r["state"],
                "state_since": r["state_since"], "kind": r["kind"], "skill": r["skill"],
                "unknown_skill": r["unknown_skill"], "now": r["headline"],
                "actions": actions.get(r["id"], []),
            }
            for r in rows
        ]

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
