"""Seam 1: a Spec Job from `/implement-spec #N`, its Steps and its Ticket DAG, through the Factory server's HTTP API."""

import pytest

import re

from test_github import SPEC_BODY, FakeGitHub, client, clock, install, issue, poll  # noqa: F401 - shared fixtures
from test_ticket_job import REPO_PATH, hook, report

SPEC = 4


class DependencyGitHub(FakeGitHub):
    """Also serves each issue's blocked-by list, as GitHub's issue dependencies API does."""

    def __init__(self) -> None:
        super().__init__()
        self.blocked_by: dict[tuple[str, int], list[int]] = {}

    def api(self, path: str):
        m = re.fullmatch(r"repos/([^/]+/[^/]+)/issues/(\d+)/dependencies/blocked_by", path)
        if not m:
            return super().api(path)
        self.reads.append(path)
        repo = m[1]
        return [issue(n, repo=repo) for n in self.blocked_by.get((repo, int(m[2])), [])]

    def block(self, repo: str, number: int, *by: int) -> None:
        """Issue `number` is blocked by `by`: its summary counts them, and the API lists them."""
        self.blocked_by[(repo, number)] = list(by)
        for i in self.issues[repo]:
            if i["number"] == number:
                i["issue_dependencies_summary"] = {"blocked_by": len(by), "total_blocked_by": len(by),
                                                   "blocking": 0, "total_blocking": 0}


@pytest.fixture
def github() -> DependencyGitHub:
    return DependencyGitHub()


def implement_spec(client, args: str = f"#{SPEC}", **over) -> dict:
    """The human typed `/implement-spec <args>`."""
    return hook(client, "UserPromptExpansion", expansion_type="slash_command", command_name="implement-spec",
                command_args=args, command_source="plugin", prompt=f"/implement-spec {args}".strip(), **over)


def jobs(client) -> list[dict]:
    return client.get("/api/state").json()["jobs"]


def steps(client) -> list[dict]:
    return client.get("/api/state").json()["steps"]


@pytest.fixture
def spec(client, github):
    """Spec #4 "Widget export" with Tickets #5 and #6, tracked but not polled yet."""
    github.issues["jeff/widgets"] = [
        issue(SPEC, "Widget export", body=SPEC_BODY, sub_issues=2),
        issue(5, "Export schema", parent=SPEC),
        issue(6, "CSV writer", parent=SPEC),
        issue(9, "Unrelated"),
    ]
    github.block("jeff/widgets", 6, 5)
    install(client)


def test_implement_spec_starts_a_spec_job_on_its_integration_branch(client, spec):
    poll(client)

    reply = implement_spec(client)

    job_id = reply["job_id"]
    [job] = jobs(client)
    assert (job["id"], job["kind"], job["number"], job["stage"]) == (job_id, "Spec Job", SPEC, "In progress")
    assert job["work_item"]["title"] == "Widget export"
    inject = reply["inject"]
    assert "git fetch" in inject
    assert "EnterWorktree" in inject and "spec-4-widget-export" in inject
    assert "current branch" in inject and "integration branch" in inject
    assert f"factory report pr <url> --job {job_id}" in inject


def test_at_job_start_each_child_ticket_of_the_spec_becomes_a_pending_step_with_its_blocking(client, spec):
    reply = implement_spec(client)  # the Spec was never polled: the Job's start reads it

    step = {"job_id": reply["job_id"], "session_id": reply["session_id"], "repo": "jeff/widgets",
            "phase": "Pending", "phase_since": "2026-10-26T12:00:00Z"}
    assert [{k: v for k, v in s.items() if k != "id"} for s in steps(client)] == [
        {**step, "number": 5, "title": "Export schema", "blocked_by": []},
        {**step, "number": 6, "title": "CSV writer", "blocked_by": [5]},
    ]
    assert reply["step_id"] is None  # the main session works no one Step


def test_tickets_added_to_the_spec_mid_job_are_picked_up_by_the_poll(client, spec, github, clock):
    implement_spec(client)

    github.issues["jeff/widgets"].append(issue(7, "Gzip the export", parent=SPEC))
    github.block("jeff/widgets", 7, 6)
    clock.advance(60)
    poll(client)

    assert [(s["number"], s["phase"], s["blocked_by"]) for s in steps(client)] == [
        (5, "Pending", []), (6, "Pending", [5]), (7, "Pending", [6]),
    ]


def test_with_github_down_at_job_start_the_steps_come_from_the_last_poll(client, spec, github):
    poll(client)
    github.down = True

    implement_spec(client)

    assert [s["number"] for s in steps(client)] == [5, 6]


CALLS = iter(range(1, 10_000))


def agent(agent_id: str) -> dict:
    """What every event of a worktree subagent carries."""
    return {"agent_id": agent_id, "agent_type": "general-purpose", "cwd": f"{REPO_PATH}/.claude/worktrees/agent-{agent_id}"}


def tool(client, name: str, tool_input: dict, response: dict | None = None, error: str | None = None, **over) -> dict:
    """One tool call, Pre then Post (or PostToolUseFailure with `error`); returns the last reply."""
    tid = f"toolu_{next(CALLS)}"
    hook(client, "PreToolUse", tool_name=name, tool_use_id=tid, tool_input=tool_input, **over)
    if error is not None:
        return hook(client, "PostToolUseFailure", tool_name=name, tool_use_id=tid, tool_input=tool_input, error=error,
                    is_interrupt=False, **over)
    return hook(client, "PostToolUse", tool_name=name, tool_use_id=tid, tool_input=tool_input,
                tool_response=response or {}, **over)


def launch(client, agent_id: str, description: str, prompt: str = "Work in your own worktree.") -> dict:
    """implement-spec launches a background worktree subagent; its PostToolUse(Agent) names the subagent."""
    tool_input = {"description": description, "prompt": prompt, "subagent_type": "general-purpose",
                  "run_in_background": True, "isolation": "worktree"}
    return tool(client, "Agent", tool_input, response={"isAsync": True, "status": "async_launched", "agentId": agent_id,
                                                         "description": description, "prompt": prompt})


def step_numbered(client, number: int) -> dict:
    return next(s for s in steps(client) if s["number"] == number)


@pytest.fixture
def job(client, spec) -> str:
    return implement_spec(client)["job_id"]


def test_a_subagent_launched_on_a_ticket_works_that_step(client, job):
    launch(client, "a1", "Implement ticket #6", "You are implementing https://github.com/jeff/widgets/issues/6 of #4.")

    reply = hook(client, "SubagentStart", **agent("a1"))
    assert reply["inject"] is None
    assert reply["step_id"] == step_numbered(client, 6)["id"]
    assert step_numbered(client, 6)["phase"] is None  # started: Phase unknown until a signal

    tool(client, "Edit", {"file_path": "/w/tests/test_csv.py"}, **agent("a1"))

    assert (step_numbered(client, 5)["phase"], step_numbered(client, 6)["phase"]) == ("Pending", "Red")


def test_the_ticket_is_parsed_from_the_prompt_when_the_description_has_none(client, job):
    launch(client, "a1", "Implementer", "Implement Ticket #5 (spec #4) test-first.")
    tool(client, "Read", {"file_path": "/w/src/schema.py"}, **agent("a1"))

    assert step_numbered(client, 5)["phase"] == "Exploring"


def test_main_session_events_and_unmapped_subagents_move_no_step(client, job):
    tool(client, "Edit", {"file_path": "/w/tests/test_x.py"})
    tool(client, "Edit", {"file_path": "/w/tests/test_y.py"}, **agent("a9"))

    assert [s["phase"] for s in steps(client)] == ["Pending", "Pending"]


def test_a_subagent_starting_before_it_is_known_is_asked_to_name_its_ticket(client, job):
    reply = hook(client, "SubagentStart", **agent("a1"))

    assert f"factory step --ticket N --job {job}" in reply["inject"]

    launch(client, "a1", "Implement ticket #6")  # its launch's PostToolUse arrives after all
    reply = hook(client, "PreToolUse", tool_name="Read", tool_use_id="t1", tool_input={}, **agent("a1"))
    assert reply["step_id"] == step_numbered(client, 6)["id"]


def test_a_subagent_that_reports_its_ticket_works_that_step(client, job):
    hook(client, "SubagentStart", **agent("a1"))

    tool(client, "Bash", {"command": f"factory step --ticket 5 --job {job}"}, **agent("a1"))
    reply = report(client, "report_step", job, ticket=5).json()

    assert reply["step_id"] == step_numbered(client, 5)["id"]
    tool(client, "Edit", {"file_path": "/w/tests/test_schema.py"}, **agent("a1"))
    assert step_numbered(client, 5)["phase"] == "Red"


@pytest.mark.parametrize("ticket", [9, "x"])
def test_a_step_report_must_name_one_of_the_specs_tickets(client, job, ticket):
    assert report(client, "report_step", job, ticket=ticket).status_code in (404, 422)


def test_a_merge_into_the_integration_branch_ends_the_step_at_merged(client, job):
    launch(client, "m1", "Merge ticket #5 into the integration branch")
    tool(client, "Bash", {"command": "git merge --no-ff worktree-agent-a1"}, **agent("m1"))

    assert step_numbered(client, 5)["phase"] == "Merged"


def test_spec_job_steps_never_reach_reviewing(client, job):
    launch(client, "a1", "Implement ticket #5")
    tool(client, "Edit", {"file_path": "/w/tests/test_schema.py"}, **agent("a1"))
    tool(client, "Skill", {"skill": "mattpocock-skills:code-review"}, **agent("a1"))
    tool(client, "Skill", {"skill": "mattpocock-skills:code-review"})

    assert step_numbered(client, 5)["phase"] == "Red"


def test_needs_you_from_a_subagent_on_a_step_names_its_ticket(client, job):
    launch(client, "a1", "Implement ticket #6")
    hook(client, "PreToolUse", tool_name="Bash", tool_use_id="t1", tool_input={"command": "rm -rf build"}, **agent("a1"))
    hook(client, "PermissionRequest", tool_name="Bash", tool_input={"command": "rm -rf build"}, **agent("a1"))

    [row] = client.get("/api/state").json()["sessions"]
    assert (row["state"], row["reason"]) == (
        "Needs you", {"kind": "permission", "tool": "Bash", "command": "rm -rf build", "step_ticket": 6})


def spec_pr(number: int, closes: tuple[int, ...], draft: bool) -> dict:
    """implement-spec's PR as GitHub's issue list returns it; its body closes the Tickets (maybe not the Spec)."""
    body = "Implements the spec.\n\n" + "\n".join(f"Closes #{n}" for n in closes)
    return {**issue(number, body=body), "html_url": f"https://github.com/jeff/widgets/pull/{number}", "draft": draft,
            "pull_request": {"merged_at": None}}


@pytest.mark.parametrize("closes", [(SPEC, 5, 6), (5, 6)])
def test_the_draft_pr_is_a_link_until_marked_ready_then_the_job_is_pr_open_and_done(client, job, github, clock, closes):
    github.issues["jeff/widgets"].append(spec_pr(60, closes, draft=True))
    clock.advance(60)
    poll(client)
    hook(client, "Stop", stop_hook_active=False, last_assistant_message="Draft PR open.")

    [state] = jobs(client)
    assert (state["stage"], state["pr"]) == ("In progress", {"number": 60, "url": "https://github.com/jeff/widgets/pull/60",
                                                            "draft": True})
    [row] = client.get("/api/state").json()["sessions"]
    assert row["state"] == "Needs you"

    github.issues["jeff/widgets"][-1]["draft"] = False
    clock.advance(60)
    poll(client)

    assert jobs(client)[0]["stage"] == "PR open"
    [row] = client.get("/api/state").json()["sessions"]
    assert (row["state"], row["seen"]) == ("Done", False)
