"""Seam 1: a Step's detail (Phase track, tests, files, commits, PR checks, review, checklist, struggle), through
the Factory server's HTTP API."""

import pytest

from conftest import SPEC_BODY, bash, edit, hook, implement, install, issue, poll, pr, read, report, tool


def detail(client, step_id: str) -> dict:
    return client.get("/api/state").json()["step_details"][step_id]


def test_the_phase_track_lists_each_phase_change_with_its_time(client, ticket, clock):
    step_id = implement(client, "#5")["step_id"]
    clock.advance(10)
    read(client)
    clock.advance(10)
    edit(client, "tests/test_api.py")
    edit(client, "tests/test_api.py")  # still Red: no new entry

    assert detail(client, step_id)["phase_events"] == [
        {"at": "2026-10-26T12:00:10Z", "from": None, "to": "Exploring"},
        {"at": "2026-10-26T12:00:20Z", "from": "Exploring", "to": "Red"},
    ]


def test_a_step_with_no_test_run_has_no_tests_pulse(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    bash(client, "ls")

    assert detail(client, step_id)["tests"] is None


def test_the_tests_pulse_follows_each_run_and_its_summary_counts(client, ticket, clock):
    step_id = implement(client, "#5")["step_id"]
    bash(client, "uv run pytest -q", exit_code=1, stdout="FAILED tests/test_api.py::test_get\n1 failed, 3 passed in 0.2s")
    clock.advance(5)
    bash(client, "npm test 2>&1 | tail -3", stdout=" Tests  4 passed (4)")

    assert detail(client, step_id)["tests"] == {
        "last": "pass",
        "passed": 4,
        "failed": 0,
        "runs": [
            {"at": "2026-10-26T12:00:00Z", "result": "fail", "passed": 3, "failed": 1},
            {"at": "2026-10-26T12:00:05Z", "result": "pass", "passed": 4, "failed": 0},
        ],
    }


def test_a_run_without_a_summary_line_has_unknown_counts(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    bash(client, "go test ./...", exit_code=2)

    tests = detail(client, step_id)["tests"]
    assert (tests["last"], tests["passed"], tests["failed"]) == ("fail", None, None)


def test_the_pulse_keeps_the_last_twelve_runs(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    for _ in range(15):
        bash(client, "pytest", stdout="2 passed")

    assert len(detail(client, step_id)["tests"]["runs"]) == 12


@pytest.fixture
def repo_rules(tmp_path, clock, github):
    """The shipped Phase rules plus test patterns of jeff/widgets' own."""
    from fastapi.testclient import TestClient

    from factory_server import create_app
    from factory_server.phases import DEFAULT_PHASE_RULES

    path = tmp_path / "phases.toml"
    path.write_text(DEFAULT_PHASE_RULES.read_text() + """
[repos."jeff/widgets"]
test_commands = ['\\bmake\\s+check\\b']
test_files = ['(^|/)checks/']
""")
    client = TestClient(create_app(db_path=tmp_path / "f.db", github=github, clock=clock, phase_rules_path=path))
    github.issues["jeff/widgets"] = [issue(4, "Widgets", body=SPEC_BODY), issue(5, "Add the widget API!", parent=4)]
    install(client)
    poll(client)
    return client


def test_a_repo_can_name_test_commands_and_files_of_its_own(repo_rules):
    step_id = implement(repo_rules, "#5")["step_id"]

    edit(repo_rules, "checks/widget_check.py")
    assert phase_of(repo_rules) == "Red"
    bash(repo_rules, "make check", stdout="ok")
    assert phase_of(repo_rules) == "Green"
    assert detail(repo_rules, step_id)["tests"]["last"] == "pass"


def phase_of(client) -> str | None:
    [step] = client.get("/api/state").json()["steps"]
    return step["phase"]


def write(client, path: str, **over) -> dict:
    return tool(client, "Write", {"file_path": path, "content": "x"}, **over)


def test_files_touched_are_listed_where_the_job_works_with_their_edit_counts(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    write(client, "/home/jeff/widgets/tests/test_api.py")
    write(client, "/home/jeff/widgets/src/api.py")
    write(client, "/home/jeff/widgets/src/api.py")
    tool(client, "Edit", {"file_path": "/home/jeff/widgets/src/b.py"}, error="String to replace not found")
    read(client, "src/c.py")
    wt = "/home/jeff/widgets/.claude/worktrees/ticket-5"
    write(client, f"{wt}/src/api.py", cwd=wt)  # in the Job's worktree, the same file
    write(client, "/tmp/scratch.txt")

    assert detail(client, step_id)["files"] == [
        {"path": "tests/test_api.py", "edits": 1, "added": None, "deleted": None},
        {"path": "src/api.py", "edits": 3, "added": None, "deleted": None},
        {"path": "/tmp/scratch.txt", "edits": 1, "added": None, "deleted": None},
    ]


def hunk(*lines: str) -> dict:
    """One hunk of the structuredPatch Claude Code's Edit and Write report in tool_response."""
    return {"oldStart": 1, "oldLines": 0, "newStart": 1, "newLines": 0, "lines": list(lines)}


def test_each_files_added_and_deleted_lines_add_up_from_its_edits_patches(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    path = "/home/jeff/widgets/src/api.py"
    tool(client, "Write", {"file_path": path, "content": "a\nb\nc\n"},
         response={"type": "create", "filePath": path, "content": "a\nb\nc\n", "structuredPatch": [], "originalFile": None})
    tool(client, "Edit", {"file_path": path, "old_string": "b", "new_string": "B\nB2"},
         response={"filePath": path, "structuredPatch": [hunk(" a", "-b", "+B", "+B2", " c")]})
    tool(client, "MultiEdit", {"file_path": path, "edits": []},
         response={"filePath": path, "structuredPatch": [hunk("-a", "+A"), hunk(" B2", "-c")]})

    assert detail(client, step_id)["files"] == [{"path": "src/api.py", "edits": 3, "added": 6, "deleted": 3}]


def test_a_write_over_a_file_counts_its_patch_not_its_whole_content(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    path = "/home/jeff/widgets/src/api.py"
    tool(client, "Write", {"file_path": path, "content": "a\nb\nc\n"},
         response={"type": "update", "filePath": path, "content": "a\nb\nc\n", "structuredPatch": [hunk(" a", "-x", "+b", " c")]})

    assert detail(client, step_id)["files"] == [{"path": "src/api.py", "edits": 1, "added": 1, "deleted": 1}]


def test_one_edit_without_a_readable_patch_leaves_the_files_lines_unknown(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    path = "/home/jeff/widgets/src/api.py"
    tool(client, "Edit", {"file_path": path, "old_string": "a", "new_string": "b"},
         response={"filePath": path, "structuredPatch": [hunk("-a", "+b")]})
    tool(client, "Edit", {"file_path": path, "old_string": "b", "new_string": "c"}, response={"filePath": path})
    tool(client, "Edit", {"file_path": path, "old_string": "c", "new_string": "d"},
         response={"filePath": path, "structuredPatch": [hunk("-c", "+d")]})

    assert detail(client, step_id)["files"] == [{"path": "src/api.py", "edits": 3, "added": None, "deleted": None}]


def test_commits_are_listed_with_their_diffstat_from_git_commits_output(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    bash(client, 'git commit -am "Add the widget API"',
         stdout="[ticket-5-add-the-widget-api 1a7c0f2] Add the widget API\n 2 files changed, 72 insertions(+), 8 deletions(-)\n")
    bash(client, "git commit -m 'Docs'", stdout="[main (root-commit) 5b2e9d4] Docs\n 1 file changed, 3 insertions(+)\n create mode 100644 README.md\n")
    bash(client, "git commit -q -m 'Quiet'")  # nothing printed: nothing to list
    bash(client, "git commit -m 'Nothing'", exit_code=1, stdout="nothing to commit, working tree clean")

    assert detail(client, step_id)["commits"] == [
        {"sha": "1a7c0f2", "message": "Add the widget API", "files": 2, "added": 72, "deleted": 8},
        {"sha": "5b2e9d4", "message": "Docs", "files": 1, "added": 3, "deleted": 0},
    ]


def check_run(name: str, status: str = "completed", conclusion: str | None = "success") -> dict:
    """A check run as GitHub's checks API lists it (only the fields the Factory reads)."""
    return {"name": name, "status": status, "conclusion": conclusion if status == "completed" else None}


def test_a_ticket_jobs_step_shows_its_pr_with_the_ci_checks_on_its_head(client, ticket, github, clock):
    step_id = implement(client, "#5")["step_id"]
    assert detail(client, step_id)["pr"] is None

    github.issues["jeff/widgets"].append(pr(50, closes=5))
    github.check_runs[("jeff/widgets", "head-50")] = [
        check_run("lint"), check_run("unit", conclusion="failure"), check_run("e2e", status="in_progress"),
        check_run("docs", conclusion="skipped"),
    ]
    clock.advance(60)
    poll(client)

    assert detail(client, step_id)["pr"] == {
        "number": 50,
        "url": "https://github.com/jeff/widgets/pull/50",
        "draft": False,
        "checks": [
            {"name": "lint", "status": "pass"},
            {"name": "unit", "status": "fail"},
            {"name": "e2e", "status": "pending"},
            {"name": "docs", "status": "skipped"},
        ],
    }


def test_a_pr_whose_checks_are_not_read_yet_shows_them_unknown(client, ticket, github):
    reply = implement(client, "#5")
    report(client, "report_pr", reply["job_id"], url="https://github.com/jeff/widgets/pull/50")
    step_id = reply["step_id"]

    assert detail(client, step_id)["pr"]["checks"] is None


def test_checks_are_read_only_for_the_prs_of_jobs_still_going(client, ticket, github, clock):
    github.issues["jeff/widgets"].append(pr(60, closes=99))  # no Job's PR
    poll(client)  # not due yet: polled by the fixture
    clock.advance(60)
    poll(client)

    assert not [r for r in github.reads if "/pulls/" in r or "check-runs" in r]


def code_review(client, **over) -> dict:
    """The agent runs code-review: the Skill call, Pre then Post; returns the Post's reply."""
    return tool(client, "Skill", {"skill": "mattpocock-skills:code-review"}, response={"success": True}, **over)


def test_code_review_asks_the_agent_to_report_its_findings_count(client, ticket):
    reply = implement(client, "#5")

    inject = code_review(client)["inject"]

    assert f"factory review --standards N --spec M --job {reply['job_id']}" in inject
    assert "--ticket" not in inject


def test_the_reported_review_findings_show_on_the_step(client, ticket):
    reply = implement(client, "#5")
    assert detail(client, reply["step_id"])["review"] is None
    code_review(client)

    assert report(client, "report_review", reply["job_id"], standards=2, spec=1).status_code == 200

    assert detail(client, reply["step_id"])["review"] == {"standards": 2, "spec": 1, "source": "report"}


SUMMARY = "**Summary:** Standards: 3 findings (worst: no tests for the error path). Spec: 0 findings."


@pytest.mark.parametrize("text, counts", [
    (SUMMARY, (3, 0)),
    ("Total findings — 2 on Standards, 1 on Spec. Worst: …", (2, 1)),
    ("Standards: no findings · Spec: 4 findings", (0, 4)),
])
def test_without_a_report_the_review_summary_line_is_read_best_effort(client, ticket, text, counts):
    reply = implement(client, "#5")
    code_review(client)

    hook(client, "MessageDisplay", delta=text)

    assert detail(client, reply["step_id"])["review"] == {"standards": counts[0], "spec": counts[1], "source": "summary"}


def test_a_summary_is_read_from_the_stopping_message_too(client, ticket):
    reply = implement(client, "#5")
    code_review(client)

    hook(client, "Stop", last_assistant_message=SUMMARY, stop_hook_active=False)

    assert detail(client, reply["step_id"])["review"]["standards"] == 3


def test_text_before_any_code_review_is_not_a_review(client, ticket):
    reply = implement(client, "#5")

    hook(client, "MessageDisplay", delta=SUMMARY)

    assert detail(client, reply["step_id"])["review"] is None


def test_the_agents_report_wins_over_the_summary_line(client, ticket):
    reply = implement(client, "#5")
    code_review(client)
    report(client, "report_review", reply["job_id"], standards=2, spec=1)

    hook(client, "MessageDisplay", delta=SUMMARY)

    assert detail(client, reply["step_id"])["review"] == {"standards": 2, "spec": 1, "source": "report"}


def test_a_review_report_needs_both_counts(client, ticket):
    reply = implement(client, "#5")

    assert report(client, "report_review", reply["job_id"], standards=2).status_code == 422


class TestSpecJob:
    """A Spec Job's Steps: each subagent's work lands on its Ticket's Step."""

    @pytest.fixture
    def github(self):
        from test_spec_job import DependencyGitHub

        return DependencyGitHub()

    @pytest.fixture
    def job(self, client, github):
        from test_spec_job import implement_spec, spec  # noqa: F401

        github.issues["jeff/widgets"] = [issue(4, "Widget export", body=SPEC_BODY, sub_issues=2),
                                         issue(5, "Export schema", parent=4), issue(6, "CSV writer", parent=4)]
        install(client)
        return implement_spec(client)["job_id"]

    def step_id(self, client, number: int) -> str:
        from test_spec_job import step_numbered

        return step_numbered(client, number)["id"]

    def test_a_subagents_work_lands_on_its_tickets_step(self, client, job):
        from test_spec_job import agent, launch
        from test_spec_job import tool as spec_tool

        launch(client, "a1", "Implement #5")
        spec_tool(client, "Bash", {"command": "pytest"}, response={"stdout": "3 passed", "stderr": ""}, **agent("a1"))

        assert detail(client, self.step_id(client, 5))["tests"]["last"] == "pass"
        assert detail(client, self.step_id(client, 6))["tests"] is None
        assert detail(client, self.step_id(client, 5))["pr"] is None  # it merges into the integration branch

    def test_a_subagents_code_review_is_asked_for_its_ticket(self, client, job):
        from test_spec_job import agent, launch

        launch(client, "a1", "Implement #5")

        inject = code_review(client, **agent("a1"))["inject"]

        assert f"--job {job} --ticket 5" in inject

    def test_the_main_sessions_review_of_the_integration_branch_is_the_whole_jobs(self, client, job):
        assert f"--job {job}`" in code_review(client)["inject"]

        report(client, "report_review", job, standards=1, spec=2)

        state = client.get("/api/state").json()
        assert state["job_reviews"] == {job: {"standards": 1, "spec": 2, "source": "report"}}
        assert all(d["review"] is None for d in state["step_details"].values())

    def test_a_review_report_can_name_its_ticket(self, client, job):
        report(client, "report_review", job, standards=0, spec=1, ticket=6)

        assert detail(client, self.step_id(client, 6))["review"] == {"standards": 0, "spec": 1, "source": "report"}


def todo(content: str, status: str = "pending") -> dict:
    return {"content": content, "status": status, "activeForm": f"Doing: {content}"}


def test_without_todo_or_task_tools_the_checklist_is_unknown(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    read(client)

    assert detail(client, step_id)["checklist"] is None


def test_the_checklist_is_the_latest_todo_list(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    first = [todo("Failing test: GET /widgets", "in_progress"), todo("Implement it")]
    tool(client, "TodoWrite", {"todos": first}, response={"oldTodos": [], "newTodos": first})
    then = [todo("Failing test: GET /widgets", "completed"), todo("Implement it", "in_progress")]
    tool(client, "TodoWrite", {"todos": then}, response={"oldTodos": first, "newTodos": then})

    assert detail(client, step_id)["checklist"] == [
        {"text": "Failing test: GET /widgets", "status": "completed"},
        {"text": "Implement it", "status": "in_progress"},
    ]


def test_the_checklist_follows_task_tools(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    hook(client, "TaskCreated", task_id="1", task_subject="Write the failing test", task_description="…")
    hook(client, "TaskCreated", task_id="2", task_subject="Make it pass", task_description="…")
    tool(client, "TaskUpdate", {"taskId": "1", "status": "in_progress"},
         response={"success": True, "taskId": "1", "statusChange": {"from": "pending", "to": "in_progress"}})
    hook(client, "TaskCompleted", task_id="1", task_subject="Write the failing test")

    assert detail(client, step_id)["checklist"] == [
        {"text": "Write the failing test", "status": "completed"},
        {"text": "Make it pass", "status": "pending"},
    ]


def struggle(client, step_id: str) -> dict | None:
    return detail(client, step_id)["struggle"]


def test_a_step_doing_fine_shows_no_struggle(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    bash(client, "pytest", exit_code=1, stdout="1 failed")
    bash(client, "pytest", exit_code=1, stdout="1 failed")
    bash(client, "pytest", stdout="2 passed")

    assert struggle(client, step_id) is None


def test_three_failing_test_runs_in_a_row_is_struggling(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    for _ in range(4):
        bash(client, "pytest", exit_code=1, stdout="1 failed")

    assert struggle(client, step_id) == {"failures": 4, "churn": [], "silent_for_s": None}

    bash(client, "pytest", stdout="2 passed")
    assert struggle(client, step_id) is None


def test_one_file_edited_five_times_without_a_passing_run_is_churn(client, ticket):
    step_id = implement(client, "#5")["step_id"]
    for _ in range(4):
        write(client, "/home/jeff/widgets/src/api.py")
    bash(client, "pytest", stdout="2 passed")
    for _ in range(4):
        write(client, "/home/jeff/widgets/src/api.py")
    assert struggle(client, step_id) is None

    write(client, "/home/jeff/widgets/src/api.py")

    assert struggle(client, step_id) == {"failures": None, "churn": ["src/api.py"], "silent_for_s": None}


def test_ten_minutes_without_a_sound_from_a_working_step_is_silence(client, ticket, clock):
    step_id = implement(client, "#5")["step_id"]
    read(client)
    clock.advance(9 * 60)
    assert struggle(client, step_id) is None

    clock.advance(60)
    assert struggle(client, step_id) == {"failures": None, "churn": [], "silent_for_s": 600}

    read(client)
    assert struggle(client, step_id) is None


def test_a_step_waiting_on_the_human_or_done_is_not_silent(client, ticket, clock):
    step_id = implement(client, "#5")["step_id"]
    hook(client, "Stop", stop_hook_active=False)  # no PR yet: Needs you
    clock.advance(30 * 60)

    assert struggle(client, step_id) is None
