"""Seam 1: the sounds the dashboard plays, scheduled by the Factory server (fake clock)."""

from test_sessions import client, clock, hook_event  # noqa: F401 - shared fixtures


def post(client, name: str, **fields) -> dict:
    return client.post("/api/events", json=hook_event(name, **fields)).json()


def sounds(client) -> list[tuple[str, str]]:
    """(sound, cc session id) for every sound the dashboard has been told to play, oldest first."""
    state = client.get("/api/state").json()
    by_id = {s["id"]: s["cc_session_id"] for s in state["sessions"]}
    return [(s["sound"], by_id.get(s["session_id"], s["session_id"])) for s in state["sounds"]]


def test_done_plays_the_done_sound_at_once(client, clock):
    post(client, "UserPromptSubmit", prompt="tidy the README")
    assert sounds(client) == []

    post(client, "Stop", background_tasks=[])

    assert sounds(client) == [("done", "cc-1")]
    [sound] = client.get("/api/state").json()["sounds"]
    assert sound["at"] == "2026-10-26T12:00:00Z"
    assert sound["machine"] == "wsl"
