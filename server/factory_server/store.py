"""SQLite state: stdlib sqlite3, no ORM."""

import json
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
-- A prompt waiting on the human (permission, question, plan approval, elicitation), in the main
-- session (agent '') or one of its subagents. key is the tool_use_id or elicitation it belongs to.
CREATE TABLE IF NOT EXISTS prompts (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL,
  agent TEXT NOT NULL,
  key TEXT,
  reason TEXT NOT NULL,
  since TEXT NOT NULL
);
-- Tool calls between PreToolUse and their PostToolUse/Failure: PermissionRequest carries no
-- tool_use_id, so its prompt is tied to the open call it asks about.
CREATE TABLE IF NOT EXISTS tool_uses (
  session_id INTEGER NOT NULL,
  agent TEXT NOT NULL,
  tool_use_id TEXT NOT NULL,
  tool_name TEXT NOT NULL,
  tool_input TEXT NOT NULL,
  PRIMARY KEY (session_id, tool_use_id)
);
"""

# Columns added to sessions after its first release; added in place to an older database.
SESSION_COLUMNS = {
    "base": "TEXT NOT NULL DEFAULT 'Working'",  # the state shown when no prompt is waiting
    "base_reason": "TEXT",
    "reason": "TEXT",  # JSON reason shown with Needs you
    "seen": "INTEGER NOT NULL DEFAULT 0",  # Done has been seen by the human
}


def iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


class Store:
    def __init__(self, path: Path) -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        have = {r["name"] for r in self.db.execute("PRAGMA table_info(sessions)")}
        with self.db:
            for name, decl in SESSION_COLUMNS.items():
                if name not in have:
                    self.db.execute(f"ALTER TABLE sessions ADD COLUMN {name} {decl}")

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
            cur = self.db.execute(
                "UPDATE sessions SET ended_at = NULL, state = 'Working', state_since = ?, base = 'Working',"
                " base_reason = NULL, reason = NULL WHERE id = ? AND ended_at IS NOT NULL",
                (iso(now), session_id),
            )
            if cur.rowcount:
                self._drop_waiting(session_id)

    def end_session(self, session_id: int, now: datetime) -> None:
        """The row ends (and stays in history); prompts it left waiting are dropped."""
        with self.db:
            self.db.execute("UPDATE sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL", (iso(now), session_id))
            self._drop_waiting(session_id)

    def _drop_waiting(self, session_id: int) -> None:
        self.db.execute("DELETE FROM prompts WHERE session_id = ?", (session_id,))
        self.db.execute("DELETE FROM tool_uses WHERE session_id = ?", (session_id,))

    def live_sessions(self) -> list[dict]:
        """Live rows, Needs you first (longest waiting first), then the rest in order of first sight."""
        rows = self.db.execute(
            "SELECT id, machine, repo, cc_session_id, state, state_since, reason, seen FROM sessions"
            " WHERE ended_at IS NULL"
            " ORDER BY state != 'Needs you', CASE WHEN state = 'Needs you' THEN state_since END, id"
        ).fetchall()
        return [
            {**dict(r), "id": str(r["id"]), "reason": r["reason"] and json.loads(r["reason"]), "seen": bool(r["seen"])}
            for r in rows
        ]

    # ---------- Needs you and Done (rules in states.py) ----------

    def set_base(self, session_id: int, base: str, reason: dict | None = None) -> None:
        """The state the session shows when no prompt is waiting; becoming Done makes it unseen."""
        with self.db:
            self.db.execute(
                "UPDATE sessions SET seen = CASE WHEN ? = 'Done' AND base != 'Done' THEN 0 ELSE seen END,"
                " base = ?, base_reason = ? WHERE id = ?",
                (base, base, None if reason is None else json.dumps(reason), session_id),
            )

    def mark_seen(self, session_id: int) -> bool:
        with self.db:
            return self.db.execute("UPDATE sessions SET seen = 1 WHERE id = ?", (session_id,)).rowcount > 0

    def open_tool_use(self, session_id: int, agent: str, tool_use_id: str, tool_name: str, tool_input: dict) -> None:
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO tool_uses VALUES (?, ?, ?, ?, ?)",
                (session_id, agent, tool_use_id, tool_name, json.dumps(tool_input, sort_keys=True)),
            )

    def close_tool_use(self, session_id: int, tool_use_id: str) -> None:
        with self.db:
            self.db.execute("DELETE FROM tool_uses WHERE session_id = ? AND tool_use_id = ?", (session_id, tool_use_id))

    def find_tool_use(self, session_id: int, agent: str, tool_name: str, tool_input: dict) -> str | None:
        """The open call a PermissionRequest asks about: the latest with that tool, same input preferred."""
        row = self.db.execute(
            "SELECT tool_use_id FROM tool_uses WHERE session_id = ? AND agent = ? AND tool_name = ?"
            " ORDER BY tool_input = ? DESC, rowid DESC LIMIT 1",
            (session_id, agent, tool_name, json.dumps(tool_input, sort_keys=True)),
        ).fetchone()
        return row["tool_use_id"] if row else None

    def add_prompt(self, session_id: int, agent: str, key: str | None, reason: dict, now: datetime) -> None:
        """A prompt starts waiting, unless one already waits for the same call."""
        with self.db:
            if key is not None and self.db.execute(
                "SELECT 1 FROM prompts WHERE session_id = ? AND key = ?", (session_id, key)
            ).fetchone():
                return
            self.db.execute(
                "INSERT INTO prompts (session_id, agent, key, reason, since) VALUES (?, ?, ?, ?, ?)",
                (session_id, agent, key, json.dumps(reason), iso(now)),
            )

    def clear_prompts(
        self, session_id: int, *, agent: str | None = None, key: str | None = None, keep: str | None = None
    ) -> None:
        """Resolve waiting prompts: all of them, or one agent's, or the one for `key`; never `keep`'s."""
        sql, args = "DELETE FROM prompts WHERE session_id = ?", [session_id]
        if agent is not None:
            sql, args = sql + " AND agent = ?", [*args, agent]
        if key is not None:
            sql, args = sql + " AND key = ?", [*args, key]
        if keep is not None:
            sql, args = sql + " AND key IS NOT ?", [*args, keep]
        with self.db:
            self.db.execute(sql, args)

    def settle(self, session_id: int, now: datetime) -> None:
        """The shown state: Needs you for the oldest waiting prompt, else the base state; since = last change."""
        prompt = self.db.execute(
            "SELECT reason FROM prompts WHERE session_id = ? ORDER BY id LIMIT 1", (session_id,)
        ).fetchone()
        with self.db:
            if prompt:
                self.db.execute(
                    "UPDATE sessions SET state_since = CASE WHEN state = 'Needs you' THEN state_since ELSE ? END,"
                    " state = 'Needs you', reason = ? WHERE id = ?",
                    (iso(now), prompt["reason"], session_id),
                )
            else:
                self.db.execute(
                    "UPDATE sessions SET state_since = CASE WHEN state = base THEN state_since ELSE ? END,"
                    " state = base, reason = base_reason WHERE id = ?",
                    (iso(now), session_id),
                )

    # ---------- Tracking ----------

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
