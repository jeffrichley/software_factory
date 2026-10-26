"""Seam 1: the Factory server's HTTP API, with GitHub and the clock faked."""

import json
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
            "state": "Working",
            "state_since": "2026-10-26T12:00:00Z",
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
