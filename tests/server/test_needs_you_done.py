"""Seam 1: Needs you and Done for any Tracked session, through the Factory server's HTTP API."""

from test_sessions import client, clock, hook_event  # noqa: F401 - shared fixtures


def post(client, name: str, **fields) -> dict:
    return client.post("/api/events", json=hook_event(name, **fields)).json()


def session(client) -> dict:
    [row] = client.get("/api/state").json()["sessions"]
    return row


def bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command, "description": "run it"}}


def test_a_permission_prompt_needs_you_with_the_tool_and_command_until_the_tool_runs(client, clock):
    post(client, "SessionStart")
    clock.advance(5)
    post(client, "PreToolUse", tool_use_id="toolu_1", **bash("git push -u origin main"))
    post(client, "PermissionRequest", **bash("git push -u origin main"))

    row = session(client)
    assert (row["state"], row["state_since"]) == ("Needs you", "2026-10-26T12:00:05Z")
    assert row["reason"] == {"kind": "permission", "tool": "Bash", "command": "git push -u origin main"}

    post(client, "PostToolUse", tool_use_id="toolu_1", tool_response={"stdout": ""}, **bash("git push -u origin main"))

    row = session(client)
    assert (row["state"], row["reason"]) == ("Working", None)


def test_a_question_needs_you_with_its_text_until_it_is_answered(client):
    ask = {"tool_name": "AskUserQuestion", "tool_input": {"questions": [
        {"question": "Which framework?", "header": "Framework", "options": [{"label": "React", "description": ""}]},
    ]}}
    post(client, "PreToolUse", tool_use_id="toolu_q", **ask)
    post(client, "PermissionRequest", **ask)

    row = session(client)
    assert (row["state"], row["reason"]) == ("Needs you", {"kind": "question", "text": "Which framework?"})

    post(client, "PostToolUseFailure", tool_use_id="toolu_q", error="User declined", is_interrupt=False, **ask)

    assert session(client)["state"] == "Working"


def test_a_plan_approval_needs_you(client):
    post(client, "PreToolUse", tool_use_id="toolu_p", tool_name="ExitPlanMode", tool_input={"plan": "# Plan\n1. do it"})

    row = session(client)
    assert (row["state"], row["reason"]) == ("Needs you", {"kind": "question", "text": "Approve the plan?"})

    post(client, "PostToolUse", tool_use_id="toolu_p", tool_name="ExitPlanMode", tool_response={})

    assert session(client)["state"] == "Working"


def test_an_mcp_elicitation_needs_you_with_its_message_until_its_result(client):
    post(client, "SessionStart")
    post(client, "Elicitation", mcp_server_name="tracker", message="Which board?", mode="form", requested_schema={})

    row = session(client)
    assert (row["state"], row["reason"]) == ("Needs you", {"kind": "question", "text": "Which board?"})

    post(client, "ElicitationResult", mcp_server_name="tracker", action="accept", content={"board": "main"})

    assert session(client)["state"] == "Working"


def read(tool_use_id: str) -> dict:
    return {"tool_use_id": tool_use_id, "tool_name": "Read", "tool_input": {"file_path": "/x"}, "tool_response": {}}


def test_a_prompt_tied_to_no_open_call_clears_when_the_session_moves_on(client):
    post(client, "PermissionRequest", **bash("rm -rf build"))
    post(client, "PermissionRequest", **bash("rm -rf build"))
    assert session(client)["state"] == "Needs you"

    post(client, "PreToolUse", **read("toolu_2"))

    assert session(client)["state"] == "Working"


def test_typing_into_the_session_clears_every_prompt(client):
    post(client, "PreToolUse", tool_use_id="toolu_3", **bash("rm -rf dist"))
    post(client, "PermissionRequest", **bash("rm -rf dist"))

    post(client, "UserPromptSubmit", prompt="no, keep dist")

    assert (session(client)["state"], session(client)["reason"]) == ("Working", None)


def test_a_sibling_tool_call_leaves_a_waiting_permission_prompt_in_place(client):
    post(client, "PreToolUse", tool_use_id="toolu_a", **bash("git push"))
    post(client, "PreToolUse", **read("toolu_b"))
    post(client, "PermissionRequest", **bash("git push"))

    post(client, "PostToolUse", **read("toolu_b"))
    post(client, "PreToolUse", **read("toolu_c"))
    post(client, "PostToolUseFailure", error="Exit code 1", **read("toolu_c"))

    assert session(client)["reason"] == {"kind": "permission", "tool": "Bash", "command": "git push"}
    post(client, "PostToolUse", tool_use_id="toolu_a", tool_response={}, **bash("git push"))
    assert session(client)["state"] == "Working"


def test_a_sibling_tool_call_leaves_a_waiting_question_in_place(client):
    post(client, "PreToolUse", tool_use_id="toolu_q", tool_name="AskUserQuestion", tool_input={"questions": [{"question": "Ship it?"}]})
    post(client, "PreToolUse", **read("toolu_b"))
    post(client, "PostToolUse", **read("toolu_b"))

    assert session(client)["reason"] == {"kind": "question", "text": "Ship it?"}


def test_two_concurrent_calls_to_one_tool_each_get_their_own_prompt(client):
    post(client, "PreToolUse", tool_use_id="toolu_1", **bash("make deploy"))
    post(client, "PreToolUse", tool_use_id="toolu_2", **bash("make deploy"))
    post(client, "PermissionRequest", **bash("make deploy"))
    post(client, "PermissionRequest", **bash("make deploy"))

    post(client, "PostToolUse", tool_use_id="toolu_2", tool_response={}, **bash("make deploy"))
    assert session(client)["state"] == "Needs you"

    post(client, "PostToolUse", tool_use_id="toolu_1", tool_response={}, **bash("make deploy"))
    assert session(client)["state"] == "Working"


def test_waiting_time_counts_from_the_first_prompt(client, clock):
    post(client, "PreToolUse", tool_use_id="toolu_1", **bash("git push"))
    post(client, "PermissionRequest", **bash("git push"))
    clock.advance(30)
    post(client, "Elicitation", mcp_server_name="tracker", message="Which board?")

    row = session(client)
    assert (row["state_since"], row["reason"]["kind"]) == ("2026-10-26T12:00:00Z", "permission")


def test_a_subagents_prompt_makes_its_parent_session_need_you(client):
    sub = {"agent_id": "a-42", "agent_type": "general-purpose"}
    post(client, "SubagentStart", **sub)
    post(client, "PreToolUse", tool_use_id="toolu_s", **sub, **bash("gh pr create"))
    post(client, "PermissionRequest", **sub, **bash("gh pr create"))

    # The parent carrying on does not answer the subagent's prompt.
    post(client, "PreToolUse", tool_use_id="toolu_m", tool_name="Read", tool_input={"file_path": "/x"})
    post(client, "PostToolUse", tool_use_id="toolu_m", tool_name="Read", tool_response={})

    row = session(client)
    assert (row["state"], row["reason"]) == ("Needs you", {"kind": "permission", "tool": "Bash", "command": "gh pr create"})

    post(client, "PostToolUse", tool_use_id="toolu_s", **sub, **bash("gh pr create"))
    assert session(client)["state"] == "Working"


def test_a_subagent_question_ends_with_the_subagent_and_subagent_stop_is_never_done(client):
    sub = {"agent_id": "a-42", "agent_type": "general-purpose"}
    post(client, "Elicitation", mcp_server_name="tracker", message="Which board?", **sub)

    post(client, "SubagentStop", last_assistant_message="All done.", background_tasks=[], **sub)

    assert session(client)["state"] == "Working"


def test_stop_with_background_tasks_running_stays_working(client):
    post(client, "UserPromptSubmit", prompt="implement it")
    running = [{"id": "t1", "type": "subagent", "status": "running", "description": "Ticket #42", "agent_type": "general-purpose"}]

    post(client, "Stop", last_assistant_message="Started the implementers.", background_tasks=running)

    assert session(client)["state"] == "Working"


def test_a_session_with_no_job_is_done_unseen_when_it_stops(client, clock):
    post(client, "UserPromptSubmit", prompt="tidy the README")
    clock.advance(90)

    post(client, "Stop", last_assistant_message="Tidied.", background_tasks=[], session_crons=[])

    row = session(client)
    assert (row["state"], row["state_since"], row["seen"], row["reason"]) == ("Done", "2026-10-26T12:01:30Z", False, None)


def test_done_is_seen_when_the_human_types_into_the_session(client):
    post(client, "Stop", background_tasks=[])

    post(client, "UserPromptSubmit", prompt="one more thing")
    post(client, "Stop", background_tasks=[])

    # Each Done is a new one, unseen until the human looks.
    assert (session(client)["state"], session(client)["seen"]) == ("Done", False)
    post(client, "UserPromptSubmit", prompt="thanks")
    assert session(client)["seen"] is True


def test_done_is_seen_when_the_human_opens_the_sessions_detail(client):
    sid = post(client, "Stop", background_tasks=[])["session_id"]

    assert client.post(f"/api/sessions/{sid}/seen").status_code == 200

    assert (session(client)["state"], session(client)["seen"]) == ("Done", True)
    assert client.post("/api/sessions/999/seen").status_code == 404


def test_a_notification_after_done_leaves_it_done(client):
    post(client, "Stop", background_tasks=[])

    post(client, "Notification", notification_type="idle_prompt", message="Claude is waiting for your input")

    assert session(client)["state"] == "Done"


def test_an_api_error_needs_you_until_the_session_resumes(client):
    post(client, "StopFailure", error="rate_limit", error_details="429 Too Many Requests")

    row = session(client)
    assert (row["state"], row["reason"]) == ("Needs you", {"kind": "error", "type": "rate_limit"})

    post(client, "UserPromptSubmit", prompt="try again")
    assert (session(client)["state"], session(client)["reason"]) == ("Working", None)


def test_session_end_ends_the_row_and_drops_its_waiting_prompts(client):
    post(client, "PreToolUse", tool_use_id="toolu_1", **bash("git push"))
    post(client, "PermissionRequest", **bash("git push"))

    post(client, "SessionEnd", reason="prompt_input_exit")
    assert client.get("/api/state").json()["sessions"] == []

    post(client, "SessionStart", source="resume")
    assert (session(client)["state"], session(client)["reason"]) == ("Working", None)


def test_needs_you_sorts_first_longest_waiting_first(client, clock):
    for s in ("a", "b", "c"):
        post(client, "SessionStart", session=s)
    post(client, "StopFailure", session="c", error="overloaded")
    clock.advance(10)
    post(client, "PreToolUse", session="b", tool_use_id="toolu_b", tool_name="ExitPlanMode", tool_input={})

    order = [(s["cc_session_id"], s["state"]) for s in client.get("/api/state").json()["sessions"]]
    assert order == [("c", "Needs you"), ("b", "Needs you"), ("a", "Working")]


def test_on_a_silent_machine_only_working_goes_stale(client, clock):
    post(client, "PreToolUse", session="asks", tool_use_id="toolu_p", tool_name="ExitPlanMode", tool_input={"plan": "1."})
    post(client, "Stop", session="done", background_tasks=[])
    post(client, "UserPromptSubmit", session="works", prompt="tidy the README")
    clock.advance(5 * 60)

    rows = {r["cc_session_id"]: r for r in client.get("/api/state").json()["sessions"]}

    assert rows["asks"]["state"] == "Needs you"
    assert rows["asks"]["reason"] == {"kind": "question", "text": "Approve the plan?"}
    assert (rows["done"]["state"], rows["done"]["seen"]) == ("Done", False)
    assert (rows["works"]["state"], rows["works"]["stale_reason"]) == ("Stale", "Machine silent")
