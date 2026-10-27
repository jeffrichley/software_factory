"""Seam 1: the Factory server's HTTP API, with GitHub and the clock faked."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from factory_server import create_app


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class FakeGitHub:
    def api(self, path: str):
        raise AssertionError(f"unexpected GitHub read: {path}")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(tmp_path, clock) -> TestClient:
    return TestClient(create_app(db_path=tmp_path / "factory.db", github=FakeGitHub(), clock=clock))


def hook_event(name: str, session: str = "cc-1", machine: str = "wsl", repo: str = "jeff/widgets", **fields) -> dict:
    return {
        "machine": machine,
        "repo": repo,
        "repo_path": f"/home/jeff/{repo.split('/')[1]}",
        "ids": {},
        "event": {"hook_event_name": name, "session_id": session, "cwd": "/home/jeff/widgets", **fields},
    }


def test_a_started_session_appears_as_working(client, clock):
    reply = client.post("/api/events", json=hook_event("SessionStart", source="startup"))

    assert reply.status_code == 200
    body = reply.json()
    assert body["session_id"]
    assert body["job_id"] is None
    assert body["server_version"] == client.get("/api/state").json()["server_version"]

    sessions = client.get("/api/state").json()["sessions"]
    assert sessions == [
        {
            "id": body["session_id"],
            "machine": "wsl",
            "repo": "jeff/widgets",
            "cc_session_id": "cc-1",
            "state": "Working",
            "state_since": "2026-10-26T12:00:00Z",
            "reason": None,
            "seen": False,
            "hidden": False,
            "kind": "ad hoc",
            "skill": None,
            "unknown_skill": None,
            "now": None,
            "actions": [],
        }
    ]


def test_events_from_one_session_keep_one_row_until_it_ends(client):
    first = client.post("/api/events", json=hook_event("SessionStart")).json()
    again = client.post("/api/events", json=hook_event("PreToolUse", tool_name="Bash")).json()
    other = client.post("/api/events", json=hook_event("SessionStart", machine="mac")).json()

    assert again["session_id"] == first["session_id"]
    assert other["session_id"] != first["session_id"]
    assert [s["machine"] for s in client.get("/api/state").json()["sessions"]] == ["wsl", "mac"]

    client.post("/api/events", json=hook_event("SessionEnd", reason="exit"))

    assert [s["machine"] for s in client.get("/api/state").json()["sessions"]] == ["mac"]


def test_the_stream_pushes_state_on_every_change(client):
    with client.stream("GET", "/api/stream") as stream:
        events = sse_states(stream.iter_lines())
        assert next(events)["sessions"] == []

        client.post("/api/events", json=hook_event("SessionStart"))

        assert [s["repo"] for s in next(events)["sessions"]] == ["jeff/widgets"]


def sse_states(lines):
    for line in lines:
        if line.startswith("data: "):
            yield json.loads(line.removeprefix("data: "))


def test_a_resumed_session_comes_back(client, clock):
    client.post("/api/events", json=hook_event("SessionStart"))
    client.post("/api/events", json=hook_event("SessionEnd", reason="exit"))
    clock.advance(60)

    client.post("/api/events", json=hook_event("SessionStart", source="resume"))

    [row] = client.get("/api/state").json()["sessions"]
    assert row["state_since"] == "2026-10-26T12:01:00Z"


def tracking_event(name: str, machine: str = "wsl", repo: str = "jeff/widgets") -> dict:
    """`repo_installed` / `repo_uninstalled`, sent by `factory install` / `uninstall`, not by a hook."""
    return {"machine": machine, "repo": repo, "repo_path": f"/home/jeff/{repo.split('/')[1]}", "event": {"hook_event_name": name}}


def test_an_installed_repo_appears_at_once(client):
    reply = client.post("/api/events", json=tracking_event("repo_installed"))

    assert reply.status_code == 200
    assert reply.json()["session_id"] is None
    assert client.get("/api/state").json()["repos"] == [{"repo": "jeff/widgets", "machines": ["wsl"]}]


def test_a_repo_lists_every_machine_that_tracks_it(client):
    client.post("/api/events", json=tracking_event("repo_installed", machine="wsl"))
    client.post("/api/events", json=tracking_event("repo_installed", machine="mac"))
    client.post("/api/events", json=tracking_event("repo_installed", machine="mac"))

    assert client.get("/api/state").json()["repos"] == [{"repo": "jeff/widgets", "machines": ["mac", "wsl"]}]


def test_uninstall_ends_only_that_machines_live_sessions_in_the_repo(client):
    for machine in ("wsl", "mac"):
        client.post("/api/events", json=tracking_event("repo_installed", machine=machine))
        client.post("/api/events", json=hook_event("SessionStart", session=f"{machine}-1", machine=machine))
    client.post("/api/events", json=hook_event("SessionStart", session="other", repo="jeff/gadgets"))

    client.post("/api/events", json=tracking_event("repo_uninstalled", machine="wsl"))

    state = client.get("/api/state").json()
    assert [(s["machine"], s["repo"]) for s in state["sessions"]] == [("mac", "jeff/widgets"), ("wsl", "jeff/gadgets")]
    assert state["repos"] == [{"repo": "jeff/widgets", "machines": ["mac"]}]


def test_a_repo_no_machine_tracks_leaves_the_dashboard(client):
    client.post("/api/events", json=tracking_event("repo_installed"))

    client.post("/api/events", json=tracking_event("repo_uninstalled"))

    assert client.get("/api/state").json()["repos"] == []


def test_health_reports_the_server_version(client):
    assert client.get("/api/health").json() == {"server_version": client.get("/api/state").json()["server_version"]}


def test_a_running_session_comes_back_after_its_repo_is_reinstalled(client, clock):
    client.post("/api/events", json=tracking_event("repo_installed"))
    first = client.post("/api/events", json=hook_event("SessionStart")).json()
    client.post("/api/events", json=tracking_event("repo_uninstalled"))
    client.post("/api/events", json=tracking_event("repo_installed"))
    clock.advance(30)

    again = client.post("/api/events", json=hook_event("PreToolUse", tool_name="Bash")).json()

    assert again["session_id"] == first["session_id"]
    [row] = client.get("/api/state").json()["sessions"]
    assert (row["state"], row["state_since"]) == ("Working", "2026-10-26T12:00:30Z")


def test_an_ended_session_stays_ended_on_its_own_session_end(client):
    client.post("/api/events", json=hook_event("SessionStart"))
    client.post("/api/events", json=hook_event("SessionEnd", reason="exit"))

    client.post("/api/events", json=hook_event("SessionEnd", reason="exit"))

    assert client.get("/api/state").json()["sessions"] == []


def test_each_machine_shows_its_live_session_count_and_when_it_was_last_seen(client, clock):
    client.post("/api/events", json=tracking_event("repo_installed", machine="mac"))
    client.post("/api/events", json=hook_event("SessionStart", session="a"))
    clock.advance(20)
    client.post("/api/events", json=hook_event("SessionStart", session="b"))
    client.post("/api/events", json=hook_event("SessionStart", session="c"))
    client.post("/api/events", json=hook_event("SessionEnd", session="c", reason="exit"))

    assert client.get("/api/state").json()["machines"] == [
        {"machine": "mac", "sessions": 0, "last_seen": "2026-10-26T12:00:00Z", "silent": False},
        {"machine": "wsl", "sessions": 2, "last_seen": "2026-10-26T12:00:20Z", "silent": False},
    ]


def test_a_machine_with_no_events_for_five_minutes_is_silent_and_its_sessions_stale(client, clock):
    client.post("/api/events", json=hook_event("SessionStart", session="w", machine="wsl"))
    clock.advance(60)
    client.post("/api/events", json=hook_event("SessionStart", session="m", machine="mac"))
    clock.advance(4 * 60)

    state = client.get("/api/state").json()

    assert [(m["machine"], m["silent"]) for m in state["machines"]] == [("mac", False), ("wsl", True)]
    wsl, mac = state["sessions"]
    assert (wsl["state"], wsl["stale_reason"], wsl["state_since"]) == ("Stale", "Machine silent", "2026-10-26T12:00:00Z")
    assert mac["state"] == "Working"
    assert "stale_reason" not in mac


def test_a_silent_machine_reporting_again_brings_its_sessions_back(client, clock):
    client.post("/api/events", json=hook_event("SessionStart"))
    clock.advance(10 * 60)

    client.post("/api/events", json=hook_event("PreToolUse", tool_name="Bash"))

    state = client.get("/api/state").json()
    assert state["machines"][0]["silent"] is False
    assert [(s["state"], s["state_since"]) for s in state["sessions"]] == [("Working", "2026-10-26T12:00:00Z")]


def test_the_stream_pushes_state_when_a_machine_goes_silent(tmp_path, clock):
    client = TestClient(create_app(db_path=tmp_path / "f.db", github=FakeGitHub(), clock=clock, refresh_s=0.05))
    client.post("/api/events", json=hook_event("SessionStart"))
    with client.stream("GET", "/api/stream") as stream:
        events = sse_states(stream.iter_lines())
        assert next(events)["sessions"][0]["state"] == "Working"

        clock.advance(5 * 60)

        assert next(events)["sessions"][0]["state"] == "Stale"


def test_a_queued_event_counts_from_when_it_happened_but_the_machine_from_when_it_arrived(client, clock):
    clock.advance(10 * 60)

    client.post("/api/events", json={**hook_event("SessionStart"), "queued_at": "2026-10-26T12:02:00Z"})

    state = client.get("/api/state").json()
    assert state["sessions"][0]["state_since"] == "2026-10-26T12:02:00Z"
    assert state["machines"][0]["last_seen"] == "2026-10-26T12:10:00Z"


def test_a_machine_tracked_before_machines_were_recorded_still_gets_a_pill(tmp_path, clock):
    db = tmp_path / "factory.db"
    old = sqlite3.connect(db)
    old.executescript(
        "CREATE TABLE tracking (repo TEXT NOT NULL, machine TEXT NOT NULL, repo_path TEXT NOT NULL,"
        " installed_at TEXT NOT NULL, PRIMARY KEY (repo, machine));"
        "INSERT INTO tracking VALUES ('jeff/widgets', 'mac', '/Users/jeff/widgets', '2026-10-26T09:00:00Z');"
    )
    old.close()
    client = TestClient(create_app(db_path=db, github=FakeGitHub(), clock=clock))

    assert client.get("/api/state").json()["machines"] == [
        {"machine": "mac", "sessions": 0, "last_seen": "2026-10-26T09:00:00Z", "silent": True},
    ]
