"""Seam 1: the GitHub poller and Work item kinds, with GitHub (`gh api`) and the clock faked."""

import json
import sys
import time

import pytest
from fastapi.testclient import TestClient

from conftest import SPEC_BODY, install, issue, poll, uninstall
from factory_server import GhCli, create_app


def test_a_tracked_repos_issues_appear_after_a_poll(client, github):
    github.issues["jeff/widgets"] = [issue(1, "Map it", labels=("wayfinder:map",))]
    install(client)

    poll(client)

    assert client.get("/api/state").json()["work_items"] == [
        {
            "repo": "jeff/widgets",
            "number": 1,
            "title": "Map it",
            "state": "open",
            "url": "https://github.com/jeff/widgets/issues/1",
            "kind": "Map",
        }
    ]


def test_each_tracked_repo_is_polled_about_once_a_minute(client, github, clock):
    install(client, repo="jeff/widgets")
    install(client, repo="jeff/gadgets")

    poll(client)
    clock.advance(30)
    poll(client)
    assert sorted(github.reads) == [
        "repos/jeff/gadgets/issues?state=all&per_page=100&page=1",
        "repos/jeff/widgets/issues?state=all&per_page=100&page=1",
    ]

    clock.advance(30)
    poll(client)
    assert len(github.reads) == 4


def test_polling_stops_when_no_machine_tracks_the_repo(client, github, clock):
    github.issues["jeff/widgets"] = [issue(1)]
    install(client, machine="wsl")
    install(client, machine="mac")
    poll(client)

    uninstall(client, machine="wsl")
    clock.advance(60)
    poll(client)
    assert len(github.reads) == 2

    uninstall(client, machine="mac")
    clock.advance(60)
    poll(client)
    assert len(github.reads) == 2
    assert client.get("/api/state").json()["work_items"] == []


def test_a_repo_no_machine_tracks_is_never_polled(client, github):
    poll(client)

    assert github.reads == []


def test_a_failed_read_keeps_the_last_poll_and_retries_a_minute_later(client, github, clock):
    github.issues["jeff/widgets"] = [issue(1, "Before", labels=("wayfinder:map",))]
    install(client)
    poll(client)

    github.down = True
    clock.advance(60)
    poll(client)
    assert [w["title"] for w in client.get("/api/state").json()["work_items"]] == ["Before"]

    github.down = False
    github.issues["jeff/widgets"] = [issue(1, "After", labels=("wayfinder:map",))]
    clock.advance(60)
    poll(client)
    assert [w["title"] for w in client.get("/api/state").json()["work_items"]] == ["After"]


def test_every_page_of_issues_is_read(client, github):
    github.issues["jeff/widgets"] = [issue(n, labels=("wayfinder:map",)) for n in range(1, 151)]
    install(client)

    poll(client)

    assert len(client.get("/api/state").json()["work_items"]) == 150


def test_a_poll_pushes_the_new_state_to_the_dashboard(client, github):
    github.issues["jeff/widgets"] = [issue(7, "Seven", labels=("wayfinder:map",))]
    install(client)

    with client.stream("GET", "/api/stream") as stream:
        events = sse_states(stream.iter_lines())
        assert next(events)["work_items"] == []

        poll(client)

        assert [w["number"] for w in next(events)["work_items"]] == [7]


def sse_states(lines):
    for line in lines:
        if line.startswith("data: "):
            yield json.loads(line.removeprefix("data: "))


def kinds(client) -> dict[int, str | None]:
    return {w["number"]: w["kind"] for w in client.get("/api/state").json()["work_items"]}


def test_work_item_kinds_come_from_github_structure(client, github):
    github.issues["jeff/widgets"] = [
        issue(1, labels=("wayfinder:map",), sub_issues=2),
        issue(2, labels=("wayfinder:grilling",), parent=1),
        issue(3, parent=1),
        issue(4, body=SPEC_BODY),
        issue(5, parent=4, body="## Parent\n\n#4\n\n## What to build\n\n..."),
        issue(6, sub_issues=1),
        issue(7, parent=6),
        issue(8, body="Just a bug."),
    ]
    install(client)

    poll(client)

    # 8 is not a Work item, so it isn't listed: never guessed.
    assert kinds(client) == {
        1: "Map",
        2: "Decision ticket",  # a Map's child, labelled with its wayfinder type
        3: "Decision ticket",  # a Map's child
        4: "Spec",  # written by to-spec
        5: "Ticket",  # a Spec's child
        6: "Spec",  # split into Tickets by to-tickets
        7: "Ticket",
    }


def test_a_ticket_split_again_has_tickets_of_its_own_at_any_depth(client, github):
    github.issues["jeff/widgets"] = [
        issue(1, body=SPEC_BODY, sub_issues=1),
        issue(2, parent=1, sub_issues=1),  # an Epic: a Spec's child split again
        issue(3, parent=2, sub_issues=1),
        issue(4, body="## Parent\n\n#3\n"),
    ]
    install(client)

    poll(client)

    assert kinds(client) == {1: "Spec", 2: "Ticket", 3: "Ticket", 4: "Ticket"}


def test_without_sub_issues_the_parent_comes_from_the_childs_body(client, github):
    github.issues["jeff/widgets"] = [
        issue(1, labels=("wayfinder:map",)),
        issue(2, body="Part of #1\n\nWhat should we call it?"),
        issue(3, body=SPEC_BODY),
        issue(4, body="## Parent\n\n#3\n\n## What to build"),
        issue(5, body="Part of #3"),
    ]
    install(client)

    poll(client)

    assert kinds(client) == {1: "Map", 2: "Decision ticket", 3: "Spec", 4: "Ticket", 5: "Ticket"}


def test_a_child_of_an_issue_that_is_not_a_work_item_is_not_one_either(client, github):
    github.issues["jeff/widgets"] = [issue(1), issue(2, parent=1), issue(3, parent=99)]
    install(client)

    poll(client)

    assert kinds(client) == {}


def test_a_parent_named_anywhere_in_the_body_counts(client, github):
    github.issues["jeff/widgets"] = [
        issue(1, labels=("wayfinder:map",)),
        issue(2, body="Some context first.\n\nPart of #1\n"),
        issue(3, body=SPEC_BODY),
        issue(4, body="Intro.\n\n## Parent\n\n#3\n"),
        issue(5, body="This is not Part of #1, it only mentions it."),
    ]
    install(client)

    poll(client)

    assert kinds(client) == {1: "Map", 2: "Decision ticket", 3: "Spec", 4: "Ticket"}


def test_a_maps_child_that_quotes_spec_headings_is_still_a_decision_ticket(client, github):
    github.issues["jeff/widgets"] = [issue(1, labels=("wayfinder:map",)), issue(2, parent=1, body=SPEC_BODY)]
    install(client)

    poll(client)

    assert kinds(client) == {1: "Map", 2: "Decision ticket"}


def test_pull_requests_are_not_work_items(client, github):
    github.issues["jeff/widgets"] = [
        issue(1, body=SPEC_BODY),
        {**issue(2, body="Closes #1"), "pull_request": {"merged_at": None}, "draft": False},
    ]
    install(client)

    poll(client)

    assert kinds(client) == {1: "Spec"}


def test_a_kind_follows_github_on_the_next_poll(client, github, clock):
    github.issues["jeff/widgets"] = [issue(1), issue(2, parent=1)]
    install(client)
    poll(client)

    github.issues["jeff/widgets"] = [issue(1, labels=("wayfinder:map",)), issue(2, parent=1, state="closed")]
    clock.advance(60)
    poll(client)

    assert kinds(client) == {1: "Map", 2: "Decision ticket"}
    assert [w["state"] for w in client.get("/api/state").json()["work_items"]] == ["open", "closed"]


def hook(client, name: str, session: str = "cc-1", **fields) -> dict:
    event = {"hook_event_name": name, "session_id": session, **fields}
    return client.post("/api/events", json={"machine": "wsl", "repo": "jeff/widgets", "repo_path": "/r", "event": event}).json()


def typed(client, command: str, args: str, session: str = "cc-1") -> dict:
    """The human typed `/<command> <args>`."""
    return hook(client, "UserPromptExpansion", session, expansion_type="slash_command", command_name=command,
                command_args=args, prompt=f"/{command} {args}")


def mismatches(client) -> list[dict]:
    return client.get("/api/state").json()["mismatches"]


@pytest.fixture
def planned(client, github):
    """A Map with a Decision ticket, and a Spec with a Ticket."""
    github.issues["jeff/widgets"] = [
        issue(1, labels=("wayfinder:map",)),
        issue(2, labels=("wayfinder:grilling",), parent=1),
        issue(4, body=SPEC_BODY),
        issue(5, parent=4),
    ]
    install(client)
    poll(client)


def test_a_skill_run_against_the_wrong_kind_of_work_item_is_flagged(client, planned):
    session = typed(client, "implement", "#4")["session_id"]

    assert mismatches(client) == [
        {"session_id": session, "skill": "implement", "repo": "jeff/widgets", "number": 4, "kind": "Spec",
         "expected": ["Ticket"]}
    ]


@pytest.mark.parametrize(
    ("command", "number"),
    [("implement", 5), ("implement-spec", 4), ("to-tickets", 4), ("wayfinder", 1), ("to-spec", 1)],
)
def test_a_skill_run_against_the_right_kind_is_not_flagged(client, planned, command, number):
    typed(client, command, f"#{number}")

    assert mismatches(client) == []


def test_implement_spec_on_a_ticket_with_sub_issues_is_not_flagged(client, github):
    github.issues["jeff/widgets"] = [issue(4, body=SPEC_BODY), issue(5, parent=4), issue(6, parent=5)]
    install(client)
    poll(client)

    typed(client, "implement-spec", "#5")

    assert mismatches(client) == []


def test_implement_spec_on_a_work_item_with_no_sub_issues_is_flagged(client, github):
    github.issues["jeff/widgets"] = [issue(4, body=SPEC_BODY)]
    install(client)
    poll(client)

    typed(client, "implement-spec", "#4")

    assert [(m["skill"], m["number"], m["kind"]) for m in mismatches(client)] == [("implement-spec", 4, "Spec")]


def test_a_skill_the_model_starts_is_checked_too(client, planned):
    hook(client, "PreToolUse", tool_name="Skill", tool_use_id="t1",
         tool_input={"skill": "mattpocock-skills:implement-spec", "args": "https://github.com/jeff/widgets/issues/5"})

    assert [(m["skill"], m["number"], m["kind"], m["expected"]) for m in mismatches(client)] == [
        ("implement-spec", 5, "Ticket", ["Spec"])
    ]


def test_skills_with_no_work_item_or_no_expected_kind_are_never_flagged(client, planned):
    typed(client, "implement", "the login bug")
    typed(client, "tdd", "#4")
    typed(client, "implement", "#8")  # not a Work item

    assert mismatches(client) == []


def test_a_mismatch_shows_once_the_poll_learns_the_kind(client, github, clock):
    install(client)
    typed(client, "implement", "#4")
    assert mismatches(client) == []

    github.issues["jeff/widgets"] = [issue(4, body=SPEC_BODY)]
    poll(client)

    assert [m["number"] for m in mismatches(client)] == [4]


def test_a_mismatch_leaves_with_its_session(client, planned):
    typed(client, "implement", "#4")

    hook(client, "SessionEnd", reason="exit")

    assert mismatches(client) == []


def test_the_real_reader_only_ever_sends_get_requests(tmp_path):
    """The Factory never writes to GitHub: every `gh api` call it makes is an explicit GET."""
    args_log = tmp_path / "gh-args.json"
    fake_gh = tmp_path / "gh.py"
    fake_gh.write_text(f"import json, sys\nopen({str(args_log)!r}, 'w').write(json.dumps(sys.argv[1:]))\nprint('[]')\n")

    assert GhCli(gh=[sys.executable, str(fake_gh)]).api("repos/jeff/widgets/issues?state=all") == []

    assert json.loads(args_log.read_text()) == ["api", "--method", "GET", "repos/jeff/widgets/issues?state=all"]


def test_a_running_server_polls_its_tracked_repos_on_its_own(tmp_path, clock, github):
    github.issues["jeff/widgets"] = [issue(1, labels=("wayfinder:map",))]
    install(TestClient(create_app(db_path=tmp_path / "factory.db", github=github, clock=clock)))

    # Entering the client starts the server's background loop, which polls at once.
    with TestClient(create_app(db_path=tmp_path / "factory.db", github=github, clock=clock)) as running:
        for _ in range(50):
            if running.get("/api/state").json()["work_items"]:
                break
            time.sleep(0.05)

        assert kinds(running) == {1: "Map"}


def pull(number: int, state: str = "open", draft: bool = False, merged: bool = False) -> dict:
    """A PR as GitHub's issue list returns it."""
    return {
        **issue(number, body="Closes #1", state=state),
        "html_url": f"https://github.com/jeff/widgets/pull/{number}",
        "draft": draft,
        "pull_request": {"merged_at": "2026-10-26T11:00:00Z" if merged else None},
    }


def test_pull_request_state_is_kept_current(client, github, clock):
    github.issues["jeff/widgets"] = [pull(10, draft=True), pull(11), pull(12, state="closed")]
    install(client)
    poll(client)

    github.issues["jeff/widgets"] = [pull(10), pull(11, state="closed", merged=True), pull(12, state="closed")]
    clock.advance(60)
    poll(client)

    prs = client.get("/api/state").json()["pull_requests"]
    assert [(p["number"], p["state"], p["draft"]) for p in prs] == [
        (10, "open", False),
        (11, "merged", False),
        (12, "closed", False),
    ]
    assert prs[0] == {
        "repo": "jeff/widgets",
        "number": 10,
        "title": "Issue 10",
        "state": "open",
        "draft": False,
        "url": "https://github.com/jeff/widgets/pull/10",
    }


def test_a_repo_retracked_within_the_minute_is_polled_at_once(client, github):
    install(client)
    poll(client)
    uninstall(client)

    install(client)
    poll(client)

    assert len(github.reads) == 2


def test_a_bad_issue_payload_skips_that_repo_and_the_rest_still_poll(client, github, clock):
    github.issues["jeff/widgets"] = [issue(1, "Before", labels=("wayfinder:map",))]
    install(client, repo="jeff/widgets")
    install(client, repo="jeff/gadgets")
    poll(client)

    github.issues["jeff/widgets"] = [{"number": 1}]  # no title, labels or url
    github.issues["jeff/gadgets"] = [issue(2, labels=("wayfinder:map",), repo="jeff/gadgets")]
    clock.advance(60)
    poll(client)

    items = client.get("/api/state").json()["work_items"]
    assert [(w["repo"], w["number"], w["title"]) for w in items] == [
        ("jeff/gadgets", 2, "Issue 2"),
        ("jeff/widgets", 1, "Before"),
    ]


def test_a_typed_skill_and_its_skill_tool_call_are_one_start(client, planned):
    typed(client, "implement", "#4")
    hook(client, "PreToolUse", tool_name="Skill", tool_use_id="t1",
         tool_input={"skill": "mattpocock-skills:implement", "args": "#4"})

    assert len(mismatches(client)) == 1


def test_typing_the_same_skill_twice_is_two_starts(client, planned):
    typed(client, "implement", "#4")
    typed(client, "implement", "#4")

    assert len(mismatches(client)) == 2


def test_an_issue_url_names_a_work_item_only_in_the_sessions_own_repo(client, planned):
    typed(client, "implement", "https://github.com/someone/else/issues/4")

    assert mismatches(client) == []


def test_once_the_server_shuts_down_a_poll_reads_no_further_repo(client, github):
    with client:  # the server starts, then shuts down (Ctrl-C)
        pass
    install(client)

    poll(client)

    assert github.reads == []
