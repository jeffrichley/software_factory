"""Seam 1: a Ticket Job from `/implement #N` to Done, through the Factory server's HTTP API."""

import pytest

from test_github import SPEC_BODY, client, clock, github, install, issue, poll  # noqa: F401 - shared fixtures

REPO_PATH = "/home/jeff/widgets"


def hook(client, name: str, session: str = "cc-1", cwd: str = REPO_PATH, **fields) -> dict:
    event = {"hook_event_name": name, "session_id": session, "cwd": cwd, **fields}
    reply = client.post("/api/events", json={"machine": "wsl", "repo": "jeff/widgets", "repo_path": REPO_PATH, "event": event})
    assert reply.status_code == 200
    return reply.json()


def implement(client, args: str, **over) -> dict:
    """The human typed `/implement <args>`."""
    return hook(client, "UserPromptExpansion", expansion_type="slash_command", command_name="implement",
                command_args=args, command_source="plugin", prompt=f"/implement {args}".strip(), **over)


def report(client, name: str, job_id: str, **fields):
    """A `factory` self-report, sent through the same event path as hook events."""
    event = {"hook_event_name": name, "job_id": job_id, **fields}
    return client.post("/api/events", json={"machine": "wsl", "repo": "jeff/widgets", "repo_path": REPO_PATH, "event": event})


def report_pr(client, job_id: str, number: int = 50):
    return report(client, "report_pr", job_id, url=f"https://github.com/jeff/widgets/pull/{number}")


def pr(number: int, closes: int, draft: bool = False, state: str = "open") -> dict:
    """A PR as GitHub's issue list returns it."""
    return {
        **issue(number, body=f"Adds the thing.\n\nCloses #{closes}\n", state=state),
        "html_url": f"https://github.com/jeff/widgets/pull/{number}",
        "draft": draft,
        "pull_request": {"merged_at": None},
    }


def jobs(client) -> list[dict]:
    return client.get("/api/state").json()["jobs"]


def session(client) -> dict:
    [row] = client.get("/api/state").json()["sessions"]
    return row


@pytest.fixture
def ticket(client, github):
    """Ticket #5 of Spec #4, polled."""
    github.issues["jeff/widgets"] = [issue(4, "Widgets", body=SPEC_BODY), issue(5, "Add the widget API!", parent=4)]
    install(client)
    poll(client)


def test_implement_with_a_ticket_starts_a_ticket_job_and_injects_how_to_work_it(client, ticket):
    reply = implement(client, "#5")

    job_id = reply["job_id"]
    assert job_id
    assert jobs(client) == [{
        "id": job_id,
        "session_id": reply["session_id"],
        "kind": "Ticket Job",
        "repo": "jeff/widgets",
        "number": 5,
        "work_item": {"title": "Add the widget API!", "url": "https://github.com/jeff/widgets/issues/5"},
        "worktree": None,
        "branch": None,
        "stage": "In progress",
        "pr": None,
        "started_at": "2026-10-26T12:00:00Z",
    }]
    inject = reply["inject"]
    assert "git fetch" in inject
    assert "EnterWorktree" in inject and "ticket-5-add-the-widget-api" in inject
    assert "non-draft PR" in inject and "Closes #5" in inject
    assert f"factory report pr <url> --job {job_id}" in inject


def test_each_typed_implement_is_a_new_job_and_replies_carry_the_latest(client, ticket):
    first = implement(client, "#5")["job_id"]
    second = implement(client, "#5")["job_id"]

    assert first != second
    assert [j["id"] for j in jobs(client)] == [first, second]
    assert [j["stage"] for j in jobs(client)] == ["In progress", "In progress"]
    assert hook(client, "PreToolUse", tool_name="Read", tool_use_id="t1", tool_input={"file_path": "/x"})["job_id"] == second
    # A subagent's events carry the parent's session_id, and inherit its Job.
    assert hook(client, "PreToolUse", agent_id="a1", agent_type="general-purpose", tool_name="Read",
                tool_use_id="t2", tool_input={"file_path": "/y"})["job_id"] == second


def test_a_session_with_no_job_replies_with_no_job_id(client, ticket):
    hook(client, "SessionStart")

    assert hook(client, "UserPromptSubmit", prompt="hello")["job_id"] is None
    assert hook(client, "UserPromptExpansion", expansion_type="slash_command", command_name="research",
                command_args="", prompt="/research")["inject"] is None
    assert jobs(client) == []


def test_without_a_ticket_number_the_job_is_asked_to_report_it_and_shows_unknown(client, ticket):
    reply = implement(client, "the widget API")
    job_id = reply["job_id"]

    assert f"factory job --issue N --job {job_id}" in reply["inject"]
    assert "ticket-<N>-<slug>" in reply["inject"]
    [job] = jobs(client)
    assert (job["number"], job["work_item"]) == (None, None)

    assert report(client, "job_issue", job_id, issue=5).json()["job_id"] == job_id

    [job] = jobs(client)
    assert (job["number"], job["work_item"]["title"]) == (5, "Add the widget API!")


def test_an_issue_url_names_the_ticket_too(client, ticket):
    implement(client, "https://github.com/jeff/widgets/issues/5")

    assert jobs(client)[0]["number"] == 5


def test_a_ticket_not_polled_yet_is_told_to_name_its_worktree_from_the_title(client):
    reply = implement(client, "#9")

    assert "ticket-9-<slug>" in reply["inject"]
    assert jobs(client) == []  # its repo isn't tracked yet


def test_a_job_started_in_a_linked_worktree_stays_there(client, ticket):
    worktree = f"{REPO_PATH}/.claude/worktrees/ticket-5-add-the-widget-api"

    reply = implement(client, "#5", cwd=worktree)

    assert "EnterWorktree" not in reply["inject"]
    assert f"already in a worktree ({worktree})" in reply["inject"]
    assert jobs(client)[0]["worktree"] == worktree


def test_the_job_follows_the_worktree_it_enters(client, ticket):
    implement(client, "#5")
    worktree = f"{REPO_PATH}/.claude/worktrees/ticket-5-add-the-widget-api"

    hook(client, "PreToolUse", tool_name="EnterWorktree", tool_use_id="t1", tool_input={"name": "ticket-5-add-the-widget-api"})
    hook(client, "PostToolUse", tool_name="EnterWorktree", tool_use_id="t1", tool_input={"name": "ticket-5-add-the-widget-api"},
         tool_response={"worktreePath": worktree, "worktreeBranch": "worktree-ticket-5-add-the-widget-api"})
    hook(client, "PreToolUse", cwd=f"{worktree}/src", tool_name="Read", tool_use_id="t2", tool_input={"file_path": "/x"})

    [job] = jobs(client)
    assert (job["worktree"], job["branch"]) == (worktree, "worktree-ticket-5-add-the-widget-api")


def test_a_reported_pr_opens_the_job_and_the_stop_after_it_is_done(client, ticket):
    job_id = implement(client, "#5")["job_id"]

    reply = report_pr(client, job_id).json()
    assert (reply["job_id"], reply["session_id"]) == (job_id, jobs(client)[0]["session_id"])
    [job] = jobs(client)
    assert job["stage"] == "PR open"
    assert job["pr"] == {"number": 50, "url": "https://github.com/jeff/widgets/pull/50", "draft": False}
    assert session(client)["state"] == "Working"

    hook(client, "Stop", stop_hook_active=False, last_assistant_message="PR opened.")

    row = session(client)
    assert (row["state"], row["seen"]) == ("Done", False)


def test_a_job_that_stops_without_a_pr_needs_you(client, ticket):
    implement(client, "#5")

    hook(client, "Stop", stop_hook_active=False, last_assistant_message="Stuck.")

    row = session(client)
    assert (row["state"], row["reason"]) == ("Needs you", {"kind": "no-pr"})


def test_the_poll_finding_the_pr_makes_a_stopped_job_done(client, ticket, github, clock):
    implement(client, "#5")
    hook(client, "Stop", stop_hook_active=False, last_assistant_message="Pushed.")
    assert session(client)["state"] == "Needs you"

    github.issues["jeff/widgets"].append(pr(51, closes=5))
    clock.advance(60)
    poll(client)

    [job] = jobs(client)
    assert (job["stage"], job["pr"]["url"]) == ("PR open", "https://github.com/jeff/widgets/pull/51")
    row = session(client)
    assert (row["state"], row["reason"], row["seen"]) == ("Done", None, False)


def test_a_draft_pr_is_only_a_link_and_the_job_is_not_done(client, ticket, github, clock):
    implement(client, "#5")
    github.issues["jeff/widgets"].append(pr(52, closes=5, draft=True))
    clock.advance(60)
    poll(client)

    hook(client, "Stop", stop_hook_active=False, last_assistant_message="Draft up.")

    [job] = jobs(client)
    assert (job["stage"], job["pr"]) == ("In progress", {"number": 52, "url": "https://github.com/jeff/widgets/pull/52", "draft": True})
    assert session(client)["reason"] == {"kind": "no-pr"}


def test_a_closed_pr_for_the_ticket_does_not_open_the_job(client, ticket, github, clock):
    github.issues["jeff/widgets"].append(pr(40, closes=5, state="closed"))
    clock.advance(60)
    poll(client)

    implement(client, "#5")

    assert jobs(client)[0]["stage"] == "In progress"


@pytest.mark.parametrize("job_id", ["", "999"])
def test_a_self_report_must_name_a_known_job(client, ticket, job_id):
    assert report_pr(client, job_id).status_code in (404, 422)
