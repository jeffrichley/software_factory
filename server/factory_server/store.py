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
"""


def iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


class Store:
    def __init__(self, path: Path) -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

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
        """A resumed session reuses its id: bring an ended row back, Working from now."""
        with self.db:
            self.db.execute(
                "UPDATE sessions SET ended_at = NULL, state = 'Working', state_since = ? WHERE id = ? AND ended_at IS NOT NULL",
                (iso(now), session_id),
            )

    def end_session(self, session_id: int, now: datetime) -> None:
        with self.db:
            self.db.execute("UPDATE sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL", (iso(now), session_id))

    def live_sessions(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT id, machine, repo, state, state_since FROM sessions WHERE ended_at IS NULL ORDER BY id"
        ).fetchall()
        return [{**dict(r), "id": str(r["id"])} for r in rows]
