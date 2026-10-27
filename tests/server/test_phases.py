"""Seam 1: each Step's Phase, inferred from hook signals through the Factory server's HTTP API."""

import pytest

from conftest import SPEC_BODY, bash, edit, hook, implement, install, issue, poll, pr, read, report, skill, tool


def steps(client) -> list[dict]:
    return client.get("/api/state").json()["steps"]


def phase(client) -> str | None:
    [step] = steps(client)
    return step["phase"]


def test_a_ticket_job_has_one_step_whose_phase_is_unknown_at_first(client, ticket):
    reply = implement(client, "#5")

    assert reply["step_id"]
    assert steps(client) == [{
        "id": reply["step_id"],
        "job_id": reply["job_id"],
        "session_id": reply["session_id"],
        "repo": "jeff/widgets",
        "number": 5,
        "title": "Add the widget API!",
        "phase": None,
        "phase_since": "2026-10-26T12:00:00Z",
        "blocked_by": [],
    }]


def test_reading_the_code_is_exploring(client, ticket, clock):
    implement(client, "#5")
    clock.advance(30)

    read(client)

    [step] = steps(client)
    assert (step["phase"], step["phase_since"]) == ("Exploring", "2026-10-26T12:00:30Z")


def test_a_tdd_cycle_moves_the_step_through_red_green_refactor_review_and_commit(client, ticket):
    implement(client, "#5")
    seen = []

    def then(action):
        action()
        seen.append(phase(client))

    then(lambda: skill(client, "mattpocock-skills:tdd"))
    then(lambda: read(client))
    then(lambda: edit(client, "tests/test_api.py"))
    then(lambda: bash(client, "uv run pytest -q", exit_code=1, stdout="1 failed, 3 passed"))
    then(lambda: edit(client, "src/widgets/api.py"))
    then(lambda: bash(client, "uv run pytest -q", stdout="4 passed"))
    then(lambda: edit(client, "src/widgets/api.py"))
    then(lambda: bash(client, "uv run pytest -q", stdout="4 passed"))
    then(lambda: skill(client, "code-review"))
    then(lambda: bash(client, 'git commit -am "Add the widget API"'))

    assert seen == ["Exploring", "Exploring", "Red", "Red", "Red", "Green", "Refactor", "Refactor", "Reviewing", "Committed"]


@pytest.mark.parametrize("path", [
    "tests/test_api.py", "src/api_test.go", "web/src/api.test.ts", "web/src/api.spec.tsx", "web/__tests__/api.tsx", "test/api.rb",
])
def test_test_files_are_recognised_by_the_usual_names(client, ticket, path):
    implement(client, "#5")

    edit(client, path)

    assert phase(client) == "Red"


def test_editing_source_before_any_test_is_not_a_tdd_phase(client, ticket):
    implement(client, "#5")
    read(client)

    edit(client, "src/widgets/api.py")
    tool(client, "Write", {"file_path": "/w/src/widgets/new.py", "content": "x"})

    assert phase(client) == "Exploring"


def test_a_piped_test_run_that_exits_0_is_read_from_its_summary_line(client, ticket):
    implement(client, "#5")
    bash(client, "npm test 2>&1 | tail -5", stdout=" Tests  2 failed | 10 passed (12)")
    assert phase(client) == "Red"

    bash(client, "npm test 2>&1 | tail -5", stdout=" Tests  12 passed (12)")
    assert phase(client) == "Green"


def test_a_test_run_in_the_background_or_interrupted_says_nothing(client, ticket):
    implement(client, "#5")
    edit(client, "tests/test_api.py")

    tool(client, "Bash", {"command": "pytest", "run_in_background": True}, response={"backgroundTaskId": "b1"})
    tool(client, "Bash", {"command": "pytest"}, error="Exit code 130", is_interrupt=True)
    bash(client, "pytest", stdout="1 failed")  # still Red; only a pass moves it on

    assert phase(client) == "Red"


def test_a_failed_commit_is_not_committed(client, ticket):
    implement(client, "#5")
    edit(client, "tests/test_api.py")

    bash(client, "git commit -m wip", exit_code=1, stdout="nothing to commit")

    assert phase(client) == "Red"


def test_a_ticket_job_merging_main_into_its_branch_is_not_merged(client, ticket):
    implement(client, "#5")
    bash(client, 'git commit -m "done"')

    bash(client, "git merge origin/main")
    bash(client, "git merge-base --is-ancestor origin/main HEAD")

    assert phase(client) == "Committed"


def test_the_jobs_pr_merging_makes_its_step_merged(client, ticket, github, clock):
    job_id = implement(client, "#5")["job_id"]
    bash(client, 'git commit -m "done"')
    report(client, "report_pr", job_id, url="https://github.com/jeff/widgets/pull/50")
    github.issues["jeff/widgets"].append(pr(50, closes=5))
    clock.advance(60)
    poll(client)
    assert phase(client) == "Committed"

    github.issues["jeff/widgets"][-1]["pull_request"]["merged_at"] = "2026-10-26T12:05:00Z"
    github.issues["jeff/widgets"][-1]["state"] = "closed"
    clock.advance(60)
    poll(client)

    [step] = steps(client)
    assert (step["phase"], step["phase_since"]) == ("Merged", "2026-10-26T12:02:00Z")


def test_nested_skills_and_subagents_inside_a_ticket_job_are_phase_signals_never_steps(client, ticket):
    implement(client, "#5")
    implementer = {"agent_id": "a1", "agent_type": "general-purpose"}
    hook(client, "SubagentStart", **implementer)

    skill(client, "mattpocock-skills:tdd", **implementer)
    edit(client, "tests/test_api.py", **implementer)
    assert phase(client) == "Red"

    skill(client, "mattpocock-skills:code-review")

    [row] = client.get("/api/state").json()["sessions"]
    assert row["kind"] == "Ticket Job"
    assert [s["phase"] for s in steps(client)] == ["Reviewing"]
    assert len(client.get("/api/state").json()["jobs"]) == 1


def test_a_session_without_a_job_has_no_steps(client, ticket):
    hook(client, "SessionStart")
    edit(client, "tests/test_api.py")

    assert steps(client) == []


# ---------- `factory phase <name> --job <id>`: the self-report fallback ----------

def test_an_agent_can_report_its_phase_and_the_rules_carry_on_from_it(client, ticket):
    job_id = implement(client, "#5")["job_id"]

    reply = report(client, "report_phase", job_id, phase="red")
    assert reply.status_code == 200
    assert (reply.json()["job_id"], reply.json()["step_id"]) == (job_id, steps(client)[0]["id"])
    assert phase(client) == "Red"

    bash(client, "pytest", stdout="5 passed")
    assert phase(client) == "Green"


def test_a_phase_report_can_name_its_ticket(client, ticket):
    job_id = implement(client, "#5")["job_id"]

    assert report(client, "report_phase", job_id, phase="Committed", ticket=5).status_code == 200
    assert phase(client) == "Committed"
    assert report(client, "report_phase", job_id, phase="Merged", ticket=6).status_code == 404
    assert phase(client) == "Committed"


@pytest.mark.parametrize("name", ["", "Testing", "unknown"])
def test_a_phase_report_must_name_a_phase(client, ticket, name):
    job_id = implement(client, "#5")["job_id"]

    reply = report(client, "report_phase", job_id, phase=name)

    assert reply.status_code == 422
    assert "Exploring" in reply.text
    assert phase(client) is None


@pytest.mark.parametrize("job_id", ["", "999"])
def test_a_phase_report_must_name_a_known_job(client, ticket, job_id):
    assert report(client, "report_phase", job_id, phase="Red").status_code in (404, 422)


# ---------- The Phase rules are an editable table ----------

RULES = """
version = 1
[signals]
explore_tools = ["Read"]
test_files = ['^/w/spec/']

[[rule]]
on = "explore"
from = ["unknown"]
to = "{to}"
"""


@pytest.fixture
def rules(tmp_path):
    path = tmp_path / "phases.toml"
    path.write_text(RULES.format(to="Exploring"))
    return path


@pytest.fixture
def ruled(tmp_path, clock, github, rules):
    from fastapi.testclient import TestClient

    from factory_server import create_app

    client = TestClient(create_app(db_path=tmp_path / "f.db", github=github, clock=clock, phase_rules_path=rules))
    github.issues["jeff/widgets"] = [issue(4, "Widgets", body=SPEC_BODY), issue(5, "Add the widget API!", parent=4)]
    install(client)
    poll(client)
    return client


def test_edits_to_the_phase_rules_apply_without_a_restart(ruled, rules):
    implement(ruled, "#5")
    rules.write_text(RULES.format(to="Reviewing"))

    read(ruled)

    assert phase(ruled) == "Reviewing"


def test_a_broken_phase_table_keeps_the_last_good_one(ruled, rules, caplog):
    implement(ruled, "#5")
    read(ruled, path="x")  # loads the good table
    implement(ruled, "#5")
    rules.write_text(RULES.format(to="Testing"))

    read(ruled)

    assert [s["phase"] for s in steps(ruled)] == ["Exploring", "Exploring"]
    assert "Phase rules" in caplog.text and "Testing" in caplog.text


def test_the_shipped_phase_rules_are_valid(client, ticket, caplog):
    implement(client, "#5")  # the server's default Phase rules

    read(client)

    assert phase(client) == "Exploring"
    assert "Phase rules" not in caplog.text


@pytest.mark.parametrize("section, error", [
    ('commit_commands = ["x"]', "may only list"),
    ('test_commands = ["("]', "bad pattern"),
])
def test_a_repo_section_may_only_add_test_patterns(ruled, rules, caplog, section, error):
    from factory_server.phases import DEFAULT_PHASE_RULES

    rules.write_text(DEFAULT_PHASE_RULES.read_text() + f'\n[repos."jeff/widgets"]\n{section}\n')
    implement(ruled, "#5")

    read(ruled)

    assert phase(ruled) is None  # rejected, with no good table before it: no signal moves a Phase
    assert "Phase rules" in caplog.text and error in caplog.text
