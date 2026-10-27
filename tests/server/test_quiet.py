"""Quiet: a Working session with no events of its own for a while, while its Machine keeps reporting."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from conftest import hook
from factory_server import create_app


def shown(client, session: str = "idle") -> dict:
    return next(s for s in client.get("/api/state").json()["sessions"] if s["cc_session_id"] == session)


def keep_machine_reporting(client, clock, minutes: int) -> None:
    """Another session on the same Machine reports every minute, so the Machine never goes silent."""
    for _ in range(minutes):
        clock.advance(60)
        hook(client, "PreToolUse", session="busy", tool_name="Read", tool_input={"file_path": "/w/a.py"})


def test_a_working_session_goes_quiet_after_ten_minutes_without_events_not_before(client, clock):
    hook(client, "SessionStart", session="idle")
    keep_machine_reporting(client, clock, 9)
    clock.advance(59)
    sounds = client.get("/api/state").json()["sounds"]

    assert shown(client)["quiet_since"] is None

    clock.advance(1)

    row = shown(client)
    assert (row["state"], row["quiet_since"]) == ("Working", "2026-10-26T12:00:00Z")
    assert client.get("/api/state").json()["sounds"] == sounds  # going quiet plays nothing


def test_the_next_event_from_a_quiet_session_clears_it(client, clock):
    hook(client, "SessionStart", session="idle")
    keep_machine_reporting(client, clock, 12)
    assert shown(client)["quiet_since"] == "2026-10-26T12:00:00Z"

    hook(client, "PreToolUse", session="idle", tool_name="Read", tool_input={"file_path": "/w/b.py"})

    assert shown(client)["quiet_since"] is None
    keep_machine_reporting(client, clock, 10)
    assert shown(client)["quiet_since"] == "2026-10-26T12:12:00Z"


def test_events_from_its_subagents_keep_a_session_from_going_quiet(client, clock):
    hook(client, "SessionStart", session="idle")
    for _ in range(15):
        clock.advance(60)
        hook(client, "PreToolUse", session="idle", agent_id="agent-1", tool_name="Read", tool_input={"file_path": "/w/a.py"})

    assert shown(client)["quiet_since"] is None


def test_a_whole_silent_machine_makes_its_sessions_stale_not_quiet(client, clock):
    hook(client, "SessionStart", session="idle")
    clock.advance(15 * 60)

    row = shown(client)
    assert (row["state"], row["stale_reason"], row["quiet_since"]) == ("Stale", "Machine silent", None)


@pytest.mark.parametrize("state, event", [
    ("Needs you", {"hook_event_name": "PermissionRequest", "tool_name": "Bash", "tool_input": {"command": "rm -rf build"}}),
    ("Done", {"hook_event_name": "Stop"}),
])
def test_only_working_sessions_go_quiet(client, clock, state, event):
    hook(client, "SessionStart", session="idle")
    name = event.pop("hook_event_name")
    hook(client, name, session="idle", **event)
    keep_machine_reporting(client, clock, 15)

    row = shown(client)
    assert (row["state"], row["quiet_since"]) == (state, None)


def test_the_quiet_threshold_is_configurable_on_the_server(tmp_path, clock, github):
    client = TestClient(create_app(db_path=tmp_path / "f.db", github=github, clock=clock, quiet_after=timedelta(minutes=3)))
    hook(client, "SessionStart", session="idle")
    keep_machine_reporting(client, clock, 3)

    assert shown(client)["quiet_since"] == "2026-10-26T12:00:00Z"


def test_a_queued_event_arriving_late_does_not_make_a_session_look_quieter(client, clock):
    hook(client, "SessionStart", session="idle")
    keep_machine_reporting(client, clock, 12)
    hook(client, "PreToolUse", session="idle", tool_name="Read", tool_input={"file_path": "/w/b.py"})
    late = {"hook_event_name": "PostToolUse", "session_id": "idle", "cwd": "/home/jeff/widgets", "tool_name": "Read"}
    client.post("/api/events", json={"machine": "wsl", "repo": "jeff/widgets", "repo_path": "/home/jeff/widgets",
                                     "event": late, "queued_at": "2026-10-26T12:01:00Z"})

    assert shown(client)["quiet_since"] is None
