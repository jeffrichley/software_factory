"""Seam 1: hiding and showing a session, from `factory hide|show` (an event) or the dashboard."""

from test_sessions import client, clock, hook_event  # noqa: F401 - shared fixtures


def post(client, name: str, **fields) -> dict:
    return client.post("/api/events", json=hook_event(name, **fields)).json()


def session(client) -> dict:
    [row] = client.get("/api/state").json()["sessions"]
    return row


def test_factory_hide_hides_the_session_and_factory_show_brings_it_back(client):
    post(client, "SessionStart")
    assert session(client)["hidden"] is False

    reply = post(client, "session_hidden")

    assert reply["session_id"] == session(client)["id"]
    assert session(client)["hidden"] is True

    post(client, "session_shown")

    assert session(client)["hidden"] is False


def test_the_dashboard_hides_and_shows_a_session(client):
    sid = post(client, "SessionStart")["session_id"]

    assert client.post(f"/api/sessions/{sid}/hide").status_code == 200
    assert session(client)["hidden"] is True

    assert client.post(f"/api/sessions/{sid}/show").status_code == 200
    assert session(client)["hidden"] is False


def test_hiding_an_unknown_session_is_not_found(client):
    assert client.post("/api/sessions/99/hide").status_code == 404


def test_a_hidden_session_stays_hidden_as_it_works_and_after_it_is_resumed(client):
    post(client, "SessionStart")
    post(client, "session_hidden")

    post(client, "PreToolUse", tool_name="Bash", tool_input=dict(command="ls"))
    post(client, "SessionEnd")
    post(client, "SessionStart", source="resume")

    assert session(client)["hidden"] is True
