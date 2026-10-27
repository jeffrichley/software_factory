"""Shared fakes, fixtures and helpers for seam 1: the Factory server's HTTP API, with GitHub and the clock faked."""

import re
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
    """Serves each repo's issues (and PRs, which GitHub lists as issues) a page at a time, each PR's head and its
    CI check runs, and records every read."""

    def __init__(self) -> None:
        self.issues: dict[str, list[dict]] = {}
        # Each PR's head commit is `head-<n>`; its check runs, by (repo, head sha), as the checks API lists them.
        self.check_runs: dict[tuple[str, str], list[dict]] = {}
        self.reads: list[str] = []
        self.down = False

    def api(self, path: str):
        self.reads.append(path)
        if self.down:
            raise RuntimeError("gh: could not reach api.github.com")
        if m := re.fullmatch(r"repos/([^/]+/[^/]+)/pulls/(\d+)", path):
            return {"number": int(m[2]), "head": {"sha": f"head-{m[2]}"}}
        if m := re.fullmatch(r"repos/([^/]+/[^/]+)/commits/([^/]+)/check-runs\?per_page=100", path):
            runs = self.check_runs.get((m[1], m[2]), [])
            return {"total_count": len(runs), "check_runs": runs}
        m = re.fullmatch(r"repos/([^/]+/[^/?]+)/issues\?state=all&per_page=(\d+)&page=(\d+)", path)
        if not m:
            raise AssertionError(f"unexpected GitHub read: {path}")
        repo, per_page, page = m[1], int(m[2]), int(m[3])
        return self.issues.get(repo, [])[(page - 1) * per_page : page * per_page]


def issue(number: int, title: str = "", labels: tuple[str, ...] = (), parent: int | None = None, body: str = "",
          state: str = "open", sub_issues: int = 0, repo: str = "jeff/widgets") -> dict:
    """An issue as GitHub's issue list returns it (only the fields the Factory reads)."""
    return {
        "number": number,
        "title": title or f"Issue {number}",
        "state": state,
        "html_url": f"https://github.com/{repo}/issues/{number}",
        "labels": [{"name": name} for name in labels],
        "body": body,
        "parent_issue_url": None if parent is None else f"https://api.github.com/repos/{repo}/issues/{parent}",
        "sub_issues_summary": {"total": sub_issues, "completed": 0, "percent_completed": 0},
    }


SPEC_BODY = "## Problem Statement\n\nIt hurts.\n\n## Solution\n\nFix it.\n\n## User Stories\n\n1. As the human...\n"


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def github() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture
def client(tmp_path, clock, github) -> TestClient:
    return TestClient(create_app(db_path=tmp_path / "factory.db", github=github, clock=clock))


def poll(client: TestClient) -> None:
    """What the server's background loop does every few seconds: poll each Tracked repo that is due."""
    client.app.state.poll_once()


def tracking(client, name: str, machine: str = "wsl", repo: str = "jeff/widgets") -> None:
    event = {"hook_event_name": name}
    client.post("/api/events", json={"machine": machine, "repo": repo, "repo_path": "/r", "event": event})


def install(client, machine: str = "wsl", repo: str = "jeff/widgets") -> None:
    tracking(client, "repo_installed", machine, repo)


def uninstall(client, machine: str = "wsl", repo: str = "jeff/widgets") -> None:
    tracking(client, "repo_uninstalled", machine, repo)


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


CALLS = iter(range(1, 10_000))


def tool(client, name: str, tool_input: dict, response: dict | None = None, error: str | None = None, **over) -> dict:
    """One tool call, Pre then Post (or PostToolUseFailure with `error`); returns the last reply."""
    tid = f"toolu_{next(CALLS)}"
    hook(client, "PreToolUse", tool_name=name, tool_use_id=tid, tool_input=tool_input, **over)
    if error is not None:
        return hook(client, "PostToolUseFailure", tool_name=name, tool_use_id=tid, tool_input=tool_input, error=error,
                    **{"is_interrupt": False, **over})
    return hook(client, "PostToolUse", tool_name=name, tool_use_id=tid, tool_input=tool_input,
                tool_response=response or {}, **over)


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


@pytest.fixture
def ticket(client, github):
    """Ticket #5 of Spec #4, polled."""
    github.issues["jeff/widgets"] = [issue(4, "Widgets", body=SPEC_BODY), issue(5, "Add the widget API!", parent=4)]
    install(client)
    poll(client)


def read(client, path: str = "src/widgets/api.py", **over) -> dict:
    return tool(client, "Read", {"file_path": f"/w/{path}"}, **over)


def edit(client, path: str, **over) -> dict:
    return tool(client, "Edit", {"file_path": f"/w/{path}", "old_string": "a", "new_string": "b"}, **over)


def bash(client, command: str, exit_code: int = 0, stdout: str = "", **over) -> dict:
    if exit_code:
        return tool(client, "Bash", {"command": command}, error=f"Exit code {exit_code}\n{stdout}", **over)
    return tool(client, "Bash", {"command": command}, response={"stdout": stdout, "stderr": "", "interrupted": False}, **over)


def skill(client, name: str, **over) -> dict:
    return hook(client, "PreToolUse", tool_name="Skill", tool_use_id=f"toolu_{next(CALLS)}", tool_input={"skill": name}, **over)


def gh(client, command: str, stdout: str = "", **over) -> dict:
    """The session runs a `gh` command through Bash."""
    return tool(client, "Bash", {"command": command, "description": "gh"}, response={"stdout": stdout, "stderr": ""}, **over)


def session(client) -> dict:
    [row] = client.get("/api/state").json()["sessions"]
    return row
