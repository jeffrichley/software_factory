"""Seam 1: the sounds the dashboard plays, scheduled by the Factory server (fake clock)."""

from fastapi.testclient import TestClient
from test_sessions import FakeGitHub, client, clock, hook_event, sse_states  # noqa: F401 - shared fixtures

from factory_server import create_app


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


def ask(question: str = "Which framework?") -> dict:
    return {"tool_name": "AskUserQuestion", "tool_input": {"questions": [{"question": question}]}}


def test_a_question_sounds_after_a_ten_second_grace(client, clock):
    post(client, "PreToolUse", tool_use_id="toolu_q", **ask())
    clock.advance(9)
    assert sounds(client) == []

    clock.advance(1)

    assert sounds(client) == [("needs_you", "cc-1")]
    assert client.get("/api/state").json()["sounds"][0]["at"] == "2026-10-26T12:00:10Z"


def test_a_question_answered_within_the_grace_never_sounds(client, clock):
    post(client, "PreToolUse", tool_use_id="toolu_q", **ask())
    clock.advance(4)
    post(client, "PostToolUse", tool_use_id="toolu_q", tool_response={}, **ask())

    clock.advance(60)

    assert sounds(client) == []


def test_an_error_stop_sounds_after_the_grace_unless_the_session_resumes(client, clock):
    post(client, "StopFailure", session="resumed", error="rate_limit")
    post(client, "StopFailure", session="left", error="overloaded")
    clock.advance(3)
    post(client, "UserPromptSubmit", session="resumed", prompt="try again")

    clock.advance(7)

    assert sounds(client) == [("needs_you", "left")]


def bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def test_a_permission_prompt_approved_quickly_at_the_terminal_is_silent(client, clock):
    post(client, "PreToolUse", tool_use_id="toolu_1", **bash("git push"))
    post(client, "PermissionRequest", **bash("git push"))
    clock.advance(3)
    post(client, "PostToolUse", tool_use_id="toolu_1", tool_response={}, **bash("git push"))

    clock.advance(60)

    assert sounds(client) == []


def test_a_permission_prompt_sounds_when_claude_code_notifies_it(client, clock):
    post(client, "PreToolUse", tool_use_id="toolu_1", **bash("git push"))
    post(client, "PermissionRequest", **bash("git push"))
    clock.advance(30)
    assert sounds(client) == []

    post(client, "Notification", notification_type="permission_prompt", message="Claude needs your permission to use Bash")

    assert sounds(client) == [("needs_you", "cc-1")]
    assert client.get("/api/state").json()["sounds"][0]["at"] == "2026-10-26T12:00:30Z"


def test_a_notification_while_a_question_waits_sounds_it_at_once_and_only_once(client, clock):
    post(client, "PreToolUse", tool_use_id="toolu_q", **ask())
    post(client, "PermissionRequest", **ask())
    clock.advance(6)
    post(client, "Notification", notification_type="permission_prompt", message="Claude needs your permission")

    clock.advance(60)

    assert sounds(client) == [("needs_you", "cc-1")]


def test_other_notifications_make_no_sound(client, clock):
    post(client, "UserPromptSubmit", prompt="go")
    post(client, "Notification", notification_type="idle_prompt", message="Claude is waiting for your input")
    post(client, "Notification", notification_type="permission_prompt", message="Claude needs your permission")

    clock.advance(60)

    assert sounds(client) == []


def test_one_sound_per_transition_never_repeated(client, clock):
    post(client, "PreToolUse", tool_use_id="toolu_1", **bash("git push"))
    post(client, "PermissionRequest", **bash("git push"))
    post(client, "Notification", notification_type="permission_prompt", message="Claude needs your permission")
    # A second prompt while the session already Needs you is the same transition.
    post(client, "Elicitation", mcp_server_name="tracker", message="Which board?")
    post(client, "Notification", notification_type="permission_prompt", message="Claude needs your permission")
    clock.advance(60)
    post(client, "PostToolUse", tool_use_id="toolu_1", tool_response={}, **bash("git push"))
    post(client, "ElicitationResult", mcp_server_name="tracker", action="accept")
    post(client, "Stop", background_tasks=[])
    post(client, "Stop", background_tasks=[])
    clock.advance(60)

    assert sounds(client) == [("needs_you", "cc-1"), ("done", "cc-1")]

    # Each new transition sounds again, and ids only grow so the dashboard plays each once.
    post(client, "UserPromptSubmit", prompt="one more thing")
    post(client, "Stop", background_tasks=[])

    assert sounds(client) == [("needs_you", "cc-1"), ("done", "cc-1"), ("done", "cc-1")]
    ids = [s["id"] for s in client.get("/api/state").json()["sounds"]]
    assert ids == sorted(set(ids))


def test_the_stream_pushes_a_sound_when_its_grace_runs_out(tmp_path, clock):
    client = TestClient(create_app(db_path=tmp_path / "f.db", github=FakeGitHub(), clock=clock, refresh_s=0.05))
    post(client, "PreToolUse", tool_use_id="toolu_q", **ask())
    with client.stream("GET", "/api/stream") as stream:
        events = sse_states(stream.iter_lines())
        assert next(events)["sounds"] == []

        clock.advance(10)

        assert [s["sound"] for s in next(events)["sounds"]] == ["needs_you"]


def test_a_session_that_ends_within_the_grace_never_sounds(client, clock):
    post(client, "PreToolUse", tool_use_id="toolu_q", **ask())
    post(client, "SessionEnd", reason="prompt_input_exit")

    clock.advance(60)

    assert sounds(client) == []
