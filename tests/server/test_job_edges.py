"""Seam 1: how Jobs end, and their edges (escalation, duplicates, rework), through the Factory server's HTTP API."""

from conftest import SPEC_BODY, hook, implement, issue, jobs, poll, pr, report, report_pr, session


def escalate(client, job_id: str, reason: str):
    return report(client, "escalate", job_id, reason=reason)


def test_an_escalating_job_needs_you_with_its_reason(client, ticket):
    job_id = implement(client, "#5")["job_id"]
    hook(client, "PreToolUse", tool_name="Bash", tool_use_id="t1", tool_input={"command": "factory escalate ..."})

    reply = escalate(client, job_id, "Should the API be public?").json()
    assert reply["job_id"] == job_id

    row = session(client)
    assert (row["state"], row["reason"]) == ("Needs you", {"kind": "escalation", "reason": "Should the API be public?"})


def test_an_escalation_waits_through_the_agent_stopping_until_the_human_answers(client, ticket, clock):
    job_id = implement(client, "#5")["job_id"]
    bash = {"tool_name": "Bash", "tool_use_id": "t1", "tool_input": {"command": "factory escalate ..."}}
    hook(client, "PreToolUse", **bash)
    escalate(client, job_id, "Which DB?")
    hook(client, "PostToolUse", **bash, tool_response={"stdout": "Reported."})
    hook(client, "Stop", stop_hook_active=False, last_assistant_message="Waiting for you.")

    row = session(client)
    assert (row["state"], row["reason"]) == ("Needs you", {"kind": "escalation", "reason": "Which DB?"})
    clock.advance(10)
    assert [s["sound"] for s in client.get("/api/state").json()["sounds"]] == ["needs_you"]

    hook(client, "UserPromptSubmit", prompt="Postgres.")

    assert (session(client)["state"], session(client)["reason"]) == ("Working", None)


def test_an_escalating_agent_that_carries_on_working_no_longer_needs_you(client, ticket):
    job_id = implement(client, "#5")["job_id"]
    escalate(client, job_id, "Which DB?")

    hook(client, "PreToolUse", tool_name="Read", tool_use_id="t2", tool_input={"file_path": "/x"})

    assert session(client)["state"] == "Working"


def test_the_job_start_injection_teaches_how_to_escalate(client, ticket):
    reply = implement(client, "#5")

    assert f'factory escalate --job {reply["job_id"]} "<reason>"' in reply["inject"]


def merged(number: int, closes: int) -> dict:
    return {**pr(number, closes, state="closed"), "pull_request": {"merged_at": "2026-10-26T13:00:00Z"}}


def test_a_merged_pr_merges_the_job(client, ticket, github, clock):
    job_id = implement(client, "#5")["job_id"]
    report_pr(client, job_id, 50)

    github.issues["jeff/widgets"] = [issue(4, "Widgets", body=SPEC_BODY), issue(5, "Add the widget API!", parent=4, state="closed"),
                                     merged(50, closes=5)]
    clock.advance(60)
    poll(client)

    assert jobs(client)[0]["stage"] == "Merged"


def test_a_closed_pr_closes_the_job(client, ticket, github, clock):
    job_id = implement(client, "#5")["job_id"]
    report_pr(client, job_id, 50)

    github.issues["jeff/widgets"].append(pr(50, closes=5, state="closed"))
    clock.advance(60)
    poll(client)

    assert jobs(client)[0]["stage"] == "Closed"


def test_a_pr_the_poll_found_still_ends_the_job_when_it_closes(client, ticket, github, clock):
    implement(client, "#5")
    github.issues["jeff/widgets"].append(pr(51, closes=5))
    clock.advance(60)
    poll(client)
    assert jobs(client)[0]["stage"] == "PR open"

    github.issues["jeff/widgets"][-1] = pr(51, closes=5, state="closed")
    clock.advance(60)
    poll(client)

    [job] = jobs(client)
    assert (job["stage"], job["pr"]["number"]) == ("Closed", 51)


def close_ticket(github) -> None:
    github.issues["jeff/widgets"][1] = issue(5, "Add the widget API!", parent=4, state="closed")


def test_a_job_whose_ticket_closes_with_no_pr_is_abandoned(client, ticket, github, clock):
    implement(client, "#5")
    hook(client, "Stop", stop_hook_active=False, last_assistant_message="Stuck.")
    assert session(client)["reason"] == {"kind": "no-pr"}

    close_ticket(github)
    clock.advance(60)
    poll(client)

    assert jobs(client)[0]["stage"] == "Abandoned"
    # Its Job is over, so the session no longer waits for a PR.
    assert session(client)["state"] == "Done"


def test_a_job_is_never_abandoned_by_time_alone(client, ticket, github, clock):
    implement(client, "#5")

    clock.advance(30 * 24 * 3600)
    poll(client)

    assert jobs(client)[0]["stage"] == "In progress"


def test_the_human_can_abandon_a_job(client, ticket):
    job_id = implement(client, "#5")["job_id"]
    hook(client, "Stop", stop_hook_active=False, last_assistant_message="Stuck.")

    assert client.post(f"/api/jobs/{job_id}/abandon").status_code == 200

    assert jobs(client)[0]["stage"] == "Abandoned"
    row = session(client)
    # The human acted on it: nothing left to tell them.
    assert (row["state"], row["seen"]) == ("Done", True)


def test_an_ended_job_says_when_it_ended_for_history(client, ticket, clock):
    job_id = implement(client, "#5")["job_id"]
    clock.advance(42 * 60)

    client.post(f"/api/jobs/{job_id}/abandon")

    job = jobs(client)[0]
    assert (job["started_at"], job["ended_at"]) == ("2026-10-26T12:00:00Z", "2026-10-26T12:42:00Z")


def test_abandoning_an_unknown_job_is_not_found(client, ticket):
    assert client.post("/api/jobs/999/abandon").status_code == 404


def test_an_abandoned_job_stays_abandoned_whatever_its_pr_does(client, ticket, github, clock):
    job_id = implement(client, "#5")["job_id"]
    client.post(f"/api/jobs/{job_id}/abandon")

    report_pr(client, job_id, 50)
    github.issues["jeff/widgets"].append(merged(50, closes=5))
    clock.advance(60)
    poll(client)

    assert jobs(client)[0]["stage"] == "Abandoned"


def implement_on(client, machine: str, session_id: str, args: str) -> dict:
    """The human typed `/implement <args>` in a session on another Machine."""
    event = {"hook_event_name": "UserPromptExpansion", "session_id": session_id, "cwd": "/w", "expansion_type": "slash_command",
             "command_name": "implement", "command_args": args, "prompt": f"/implement {args}"}
    return client.post("/api/events", json={"machine": machine, "repo": "jeff/widgets", "repo_path": "/w", "event": event}).json()


def test_a_second_job_on_a_ticket_with_an_active_job_is_flagged_duplicate_not_blocked(client, ticket):
    first = implement(client, "#5")
    second = implement_on(client, "mac", "cc-9", "#5")

    assert [(j["id"], j["duplicate_of"]) for j in jobs(client)] == [(first["job_id"], None), (second["job_id"], first["job_id"])]
    assert "duplicate" in second["inject"] and f"Job {first['job_id']}" in second["inject"]
    assert "duplicate" not in first["inject"]
    assert "EnterWorktree" in second["inject"]  # still told how to work it


def test_a_polled_pr_closing_the_ticket_is_the_original_jobs_not_its_duplicates(client, ticket, github, clock):
    first = implement(client, "#5")["job_id"]
    implement_on(client, "mac", "cc-9", "#5")

    github.issues["jeff/widgets"].append(pr(51, closes=5))
    clock.advance(60)
    poll(client)

    assert [(j["id"] == first, j["stage"], j["pr"] and j["pr"]["number"]) for j in jobs(client)] == [
        (True, "PR open", 51), (False, "In progress", None)]


def test_a_pr_one_job_reported_is_never_borrowed_by_another_job_on_the_ticket(client, ticket, github, clock):
    implement(client, "#5")
    second = implement_on(client, "mac", "cc-9", "#5")["job_id"]
    report_pr(client, second, 51)

    github.issues["jeff/widgets"].append(pr(51, closes=5))
    clock.advance(60)
    poll(client)

    assert [(j["stage"], j["pr"] and j["pr"]["number"]) for j in jobs(client)] == [("In progress", None), ("PR open", 51)]


def test_a_job_on_a_ticket_whose_earlier_job_ended_is_not_a_duplicate(client, ticket):
    first = implement(client, "#5")["job_id"]
    client.post(f"/api/jobs/{first}/abandon")

    second = implement_on(client, "mac", "cc-9", "#5")

    assert jobs(client)[1]["duplicate_of"] is None
    assert "duplicate" not in second["inject"]


def test_a_job_that_reports_a_ticket_already_being_worked_is_flagged_duplicate(client, ticket):
    first = implement(client, "#5")["job_id"]
    second = implement_on(client, "mac", "cc-9", "the widget API")["job_id"]

    report(client, "job_issue", second, issue=5)

    assert jobs(client)[1]["duplicate_of"] == first


def test_follow_up_work_after_the_pr_stays_the_same_job_and_is_done_again_unseen(client, ticket):
    job_id = implement(client, "#5")["job_id"]
    report_pr(client, job_id, 50)
    hook(client, "Stop", stop_hook_active=False, last_assistant_message="PR opened.")
    client.post(f"/api/sessions/{session(client)['id']}/seen")

    assert hook(client, "UserPromptSubmit", prompt="CI is red, fix it.")["job_id"] == job_id
    assert session(client)["state"] == "Working"
    hook(client, "PreToolUse", tool_name="Bash", tool_use_id="t1", tool_input={"command": "pytest"})
    hook(client, "Stop", stop_hook_active=False, last_assistant_message="Fixed and pushed.")

    assert [(j["id"], j["stage"]) for j in jobs(client)] == [(job_id, "PR open")]
    row = session(client)
    assert (row["state"], row["seen"]) == ("Done", False)
