"""Seam 1: History replay — each Job's timeline (Phase changes and events over time) through the Factory server's HTTP API."""

from test_github import SPEC_BODY, client, clock, github, install, issue, poll  # noqa: F401 - shared fixtures
from test_phases import bash, edit, read, skill, ticket  # noqa: F401
from test_ticket_job import hook, implement, jobs, pr, report_pr


def replay(client, job_id: str) -> dict:
    reply = client.get(f"/api/jobs/{job_id}/replay")
    assert reply.status_code == 200
    return reply.json()


def events(client, job_id: str, *kinds: str) -> list[tuple]:
    """The replay's events as (seconds since the Job started, kind, text), only those `kinds` when given."""
    r = replay(client, job_id)
    return [(e["t"], e["kind"], e["text"]) for e in r["events"] if not kinds or e["kind"] in kinds]


def test_a_replay_starts_with_the_job_and_tracks_each_phase_change_over_time(client, ticket, clock):
    reply = implement(client, "#5")
    job_id, step_id = reply["job_id"], reply["step_id"]
    clock.advance(30)
    read(client)
    clock.advance(60)
    edit(client, "tests/test_api.py")

    r = replay(client, job_id)

    assert r["job_id"] == job_id
    assert r["started_at"] == "2026-10-26T12:00:00Z"
    assert r["steps"] == [{"id": step_id, "number": 5, "title": "Add the widget API!", "phase": None}]
    assert [(e["t"], e["kind"], e["step_id"], e["phase"]) for e in r["events"] if e["kind"] == "phase"] == [
        (30, "phase", step_id, "Exploring"),
        (90, "phase", step_id, "Red"),
    ]
    assert r["events"][0] == {"t": 0, "at": "2026-10-26T12:00:00Z", "kind": "start", "text": "Job started: #5",
                              "step_id": None, "phase": None}


def test_test_runs_commits_and_reviews_are_events_on_the_timeline(client, ticket, clock):
    job_id = implement(client, "#5")["job_id"]
    clock.advance(10)
    bash(client, "uv run pytest -q", exit_code=1, stdout="1 failed, 3 passed")
    clock.advance(10)
    bash(client, "uv run pytest -q", stdout="4 passed")
    clock.advance(10)
    skill(client, "code-review")
    clock.advance(10)
    bash(client, 'git commit -am "Add the widget API"')

    assert events(client, job_id, "test_pass", "test_fail", "review", "commit") == [
        (10, "test_fail", "Tests fail: uv run pytest -q"),
        (20, "test_pass", "Tests pass: uv run pytest -q"),
        (30, "review", "Review: code-review"),
        (40, "commit", 'Commit: git commit -am "Add the widget API"'),
    ]


def test_what_the_agent_does_is_on_the_timeline_as_actions(client, ticket, clock):
    job_id = implement(client, "#5")["job_id"]
    clock.advance(5)
    read(client)

    (t, _, text) = events(client, job_id, "action")[-1]
    assert t == 5 and "api.py" in text


def test_each_time_the_job_needs_you_is_an_event_saying_why(client, ticket, clock):
    job_id = implement(client, "#5")["job_id"]
    clock.advance(20)
    hook(client, "PermissionRequest", tool_name="Bash", tool_input={"command": "rm -rf build"})
    hook(client, "PermissionRequest", tool_name="Bash", tool_input={"command": "rm -rf build"})  # still the same wait
    clock.advance(5)
    hook(client, "UserPromptSubmit", prompt="ok")
    clock.advance(30)
    hook(client, "Stop", stop_hook_active=False, last_assistant_message="Stuck.")

    assert events(client, job_id, "needs") == [
        (20, "needs", "Needs you: permission for Bash: rm -rf build"),
        (55, "needs", "Needs you: ended without a PR"),
    ]


def merged(number: int, closes: int) -> dict:
    return {**pr(number, closes, state="closed"), "pull_request": {"merged_at": "2026-10-26T13:00:00Z"}}


def test_the_pr_and_the_jobs_end_close_the_timeline(client, ticket, github, clock):
    job_id = implement(client, "#5")["job_id"]
    clock.advance(600)
    report_pr(client, job_id, 50)
    github.issues["jeff/widgets"][1] = issue(5, "Add the widget API!", parent=4, state="closed")
    github.issues["jeff/widgets"].append(merged(50, closes=5))
    clock.advance(60)
    poll(client)
    clock.advance(60)
    poll(client)  # still Merged: it ended once

    assert events(client, job_id, "pr", "end") == [
        (600, "pr", "PR: https://github.com/jeff/widgets/pull/50"),
        (660, "end", "Merged"),
    ]
    assert replay(client, job_id)["ended_at"] == "2026-10-26T12:11:00Z"


def test_a_job_abandoned_on_the_dashboard_ends_its_timeline(client, ticket, clock):
    job_id = implement(client, "#5")["job_id"]
    clock.advance(90)

    client.post(f"/api/jobs/{job_id}/abandon")

    assert events(client, job_id, "end") == [(90, "end", "Abandoned")]
    assert replay(client, job_id)["ended_at"] == "2026-10-26T12:01:30Z"


def test_a_running_job_has_no_end_yet(client, ticket):
    job_id = implement(client, "#5")["job_id"]

    assert replay(client, job_id)["ended_at"] is None


def test_a_job_that_does_not_exist_has_no_replay(client):
    assert client.get("/api/jobs/99/replay").status_code == 404


def test_each_job_names_its_machine_so_history_can_follow_the_machine_filter(client, ticket):
    implement(client, "#5")

    assert [j["machine"] for j in jobs(client)] == ["wsl"]
