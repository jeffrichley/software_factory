"""SQLite state: stdlib sqlite3, no ORM."""

import sqlite3
from datetime import datetime
from pathlib import Path

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
"""
# Columns added after the first release, so an existing database gains them on start.
SESSION_COLUMNS = {
    "kind": "TEXT NOT NULL DEFAULT 'ad hoc'",
    "skill": "TEXT",
    "headline": "TEXT",
    "mattpocock_skills_version": "TEXT",
}
# The ad hoc detail view's timeline shows a session's last few actions; older ones are dropped.
KEEP_ACTIONS = 8


def iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


class Store:
    def __init__(self, path: Path) -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        have = {r["name"] for r in self.db.execute("PRAGMA table_info(sessions)")}
        with self.db:
            for column, decl in SESSION_COLUMNS.items():
                if column not in have:
                    self.db.execute(f"ALTER TABLE sessions ADD COLUMN {column} {decl}")

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

    def resume_session(self, session_id: int, now: datetime) -> None:
        """An ended session that is active again keeps its id: bring its row back, Working from now."""
        with self.db:
            self.db.execute(
                "UPDATE sessions SET ended_at = NULL, state = 'Working', state_since = ? WHERE id = ? AND ended_at IS NOT NULL",
                (iso(now), session_id),
            )

    def end_session(self, session_id: int, now: datetime) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL", (iso(now), session_id))

    def set_mattpocock_skills_version(self, session_id: int, version: str | None) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET mattpocock_skills_version = ? WHERE id = ?", (version, session_id))

    def session(self, session_id: int) -> sqlite3.Row:
        return self.db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()

    def classify(self, session_id: int, kind: str, skill: str | None) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET kind = ?, skill = ? WHERE id = ?", (kind, skill, session_id))

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

    def live_sessions(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT id, machine, repo, state, state_since, kind, skill, headline FROM sessions WHERE ended_at IS NULL ORDER BY id"
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
                "state_since": r["state_since"], "kind": r["kind"], "skill": r["skill"], "now": r["headline"],
                "actions": actions.get(r["id"], []),
            }
            for r in rows
        ]

    def track_repo(self, repo: str, machine: str, repo_path: str, now: datetime) -> None:
        """This Machine tracks the repo; tracking it again keeps the first install time."""
        with self.db:
            self.db.execute(
                "INSERT INTO tracking (repo, machine, repo_path, installed_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT (repo, machine) DO UPDATE SET repo_path = excluded.repo_path",
                (repo, machine, repo_path, iso(now)),
            )

    def untrack_repo(self, repo: str, machine: str, now: datetime) -> None:
        """The Machine stops tracking the repo: its live sessions there end (and stay in history)."""
        with self.db:
            self.db.execute("DELETE FROM tracking WHERE repo = ? AND machine = ?", (repo, machine))
            self.db.execute(
                "UPDATE sessions SET ended_at = ? WHERE repo = ? AND machine = ? AND ended_at IS NULL",
                (iso(now), repo, machine),
            )

    def tracked_repos(self) -> list[dict]:
        rows = self.db.execute("SELECT repo, machine FROM tracking ORDER BY repo, machine").fetchall()
        repos: dict[str, list[str]] = {}
        for r in rows:
            repos.setdefault(r["repo"], []).append(r["machine"])
        return [{"repo": repo, "machines": machines} for repo, machines in repos.items()]
