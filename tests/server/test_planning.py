"""Seam 1: research, to-spec and to-tickets sessions show the plan taking shape, through the Factory server's HTTP API."""

import pytest

from test_github import client, clock, install, issue, poll  # noqa: F401 - shared fixtures
from test_spec_job import DependencyGitHub, tool
from test_ticket_job import REPO_PATH, hook
from test_wayfinder import gh

QUESTION = "Can a hook see a test runner's exit code?"


def typed(client, skill: str, args: str = "", **over) -> dict:
    """The human typed `/<skill> <args>`."""
    return hook(client, "UserPromptExpansion", expansion_type="slash_command", command_name=skill,
                command_args=args, command_source="plugin", prompt=f"/{skill} {args}".strip(), **over)


def state(client) -> dict:
    return client.get("/api/state").json()


def session(client) -> dict:
    [row] = state(client)["sessions"]
    return row


def facts(client, key: str) -> dict:
    """The one live session's planning facts under `key` in the dashboard state."""
    [row] = state(client)[key]
    assert row["session_id"] == session(client)["id"]
    return row


@pytest.fixture
def github() -> DependencyGitHub:
    return DependencyGitHub()


@pytest.fixture
def tracked(client):
    install(client)


# A research session spins up a background agent; its tool calls carry the agent_id.
AGENT = {"agent_id": "a1", "agent_type": "general-purpose"}


def test_a_research_session_shows_its_question_searches_sources_and_findings(client, tracked):
    typed(client, "research", QUESTION)
    tool(client, "WebSearch", {"query": "claude code hooks PostToolUse payload"}, response={}, **AGENT)
    tool(client, "WebFetch", {"url": "https://code.claude.com/docs/en/hooks", "prompt": "exit code"}, response={}, **AGENT)
    tool(client, "WebSearch", {"query": "pytest exit codes"}, response={}, **AGENT)
    tool(client, "WebFetch", {"url": "https://docs.pytest.org/en/stable/reference/exit-codes.html", "prompt": "codes"},
         response={}, **AGENT)
    tool(client, "Write", {"file_path": f"{REPO_PATH}/docs/research/hook-exit-codes.md", "content": "# Findings\n"},
         response={"type": "create"}, **AGENT)

    r = facts(client, "research")
    assert r["question"] == QUESTION
    assert r["searches"] == ["claude code hooks PostToolUse payload", "pytest exit codes"]
    assert r["sources"] == ["https://code.claude.com/docs/en/hooks",
                            "https://docs.pytest.org/en/stable/reference/exit-codes.html"]
    assert r["findings"] == {"path": "docs/research/hook-exit-codes.md",
                             "url": "https://github.com/jeff/widgets/blob/HEAD/docs/research/hook-exit-codes.md"}


def test_a_research_session_knows_nothing_until_it_does(client, tracked):
    typed(client, "research")

    r = facts(client, "research")
    assert (r["question"], r["searches"], r["sources"], r["findings"]) == (None, [], [], None)


def test_a_research_session_stays_working_while_its_agent_reads_and_is_done_on_stop(client, tracked):
    typed(client, "research", QUESTION)
    hook(client, "Stop", last_assistant_message="Researching in the background.",
         background_tasks=[{"id": "a1", "status": "running"}])
    assert session(client)["state"] == "Working"

    hook(client, "Stop", last_assistant_message="Findings written.", background_tasks=[])
    assert (session(client)["kind"], session(client)["state"]) == ("research", "Done")


MAP = 1
SPEC_DRAFT = """## Problem Statement

Exports are manual.

## Solution

An exporter.

## User Stories

1. As the human, I want a CSV, so that I can share it.
"""
SPEC_REST = """## Implementation Decisions

- CSV first.

## Testing Decisions

- Through the CLI.

## Out of Scope

- PDF.

## Further Notes

None.
"""


def outline(client) -> list[tuple[str, bool]]:
    return [(o["section"], o["written"]) for o in facts(client, "to_spec")["outline"]]


@pytest.fixture
def charted(client, github):
    """Map #1, tracked and polled."""
    github.issues["jeff/widgets"] = [issue(MAP, "Widgets: chart the way to a spec", labels=("wayfinder:map",))]
    install(client)
    poll(client)


def test_a_to_spec_session_shows_its_map_and_ticks_the_spec_sections_as_it_writes_them(client, charted):
    typed(client, "to-spec", f"#{MAP}")
    assert facts(client, "to_spec")["map"] == MAP
    assert not any(written for _, written in outline(client))

    tool(client, "Write", {"file_path": "/tmp/spec.md", "content": SPEC_DRAFT}, response={"type": "create"})

    assert outline(client) == [("Problem Statement", True), ("Solution", True), ("User Stories", True),
                               ("Implementation Decisions", False), ("Testing Decisions", False),
                               ("Out of Scope", False), ("Further Notes", False)]
    assert facts(client, "to_spec")["spec"] is None


def test_a_to_spec_session_publishing_its_spec_ticks_every_section_it_has_and_links_the_spec(client, charted):
    typed(client, "to-spec", f"#{MAP}")
    tool(client, "Write", {"file_path": f"{REPO_PATH}/.scratch/spec.md", "content": SPEC_DRAFT + SPEC_REST},
         response={"type": "create"})
    gh(client, 'gh issue create --title "Spec: the widget exporter" --label ready-for-agent --body-file .scratch/spec.md',
       stdout="https://github.com/jeff/widgets/issues/12\n")

    assert all(written for _, written in outline(client))
    assert facts(client, "to_spec")["spec"] == 12


def test_a_spec_published_with_an_inline_body_ticks_its_sections(client, charted):
    typed(client, "to-spec", f"#{MAP}")
    gh(client, f"gh issue create --title \"Spec: exporter\" --body \"$(cat <<'EOF'\n{SPEC_DRAFT}EOF\n)\"",
       stdout="https://github.com/jeff/widgets/issues/12\n")

    assert [s for s, written in outline(client) if written] == ["Problem Statement", "Solution", "User Stories"]


def test_without_a_map_in_its_args_a_to_spec_session_takes_the_map_it_reads(client, charted):
    typed(client, "to-spec")
    assert facts(client, "to_spec")["map"] is None

    gh(client, f"gh issue view {MAP} --comments", stdout="Widgets: chart the way to a spec\n")
    assert facts(client, "to_spec")["map"] == MAP


def test_to_spec_after_wayfinder_in_the_same_session_comes_from_its_map(client, charted):
    typed(client, "wayfinder", f"#{MAP}")
    typed(client, "to-spec")

    assert (session(client)["kind"], facts(client, "to_spec")["map"]) == ("to-spec", MAP)


def test_a_to_spec_session_is_done_on_stop(client, charted):
    typed(client, "to-spec", f"#{MAP}")
    hook(client, "Stop", last_assistant_message="Spec published.", background_tasks=[])

    assert session(client)["state"] == "Done"


SPEC = 12


def ticket_body(blocked_by: str = "None (can start immediately)") -> str:
    return (f"## Parent\n\n#{SPEC}\n\n## What to build\n\nA slice.\n\n## Acceptance criteria\n\n- [ ] It works\n\n"
            f"## Blocked by\n\n{blocked_by}\n")


def create_ticket(client, number: int, title: str, blocked_by: str = "None (can start immediately)") -> None:
    gh(client, f"gh issue create --title \"{title}\" --label ready-for-agent --body \"$(cat <<'EOF'\n"
               f"{ticket_body(blocked_by)}EOF\n)\"",
       stdout=f"https://github.com/jeff/widgets/issues/{number}\n")


def tickets(client) -> list[tuple]:
    return [(t["number"], t["title"], t["state"], t["blocked_by"]) for t in facts(client, "to_tickets")["tickets"]]


@pytest.fixture
def specced(client, github):
    """Spec #12, tracked and polled."""
    github.issues["jeff/widgets"] = [issue(SPEC, "Spec: the widget exporter", body="## Problem Statement\n\n## Solution\n")]
    install(client)
    poll(client)


def test_a_to_tickets_session_shows_its_spec_and_each_ticket_it_creates_with_its_blockers(client, specced):
    typed(client, "to-tickets", f"#{SPEC}")
    assert (facts(client, "to_tickets")["spec"], tickets(client)) == (SPEC, [])

    create_ticket(client, 13, "Export one table to CSV")
    create_ticket(client, 14, "Export every table", blocked_by="- #13")
    create_ticket(client, 15, "Escape awkward values", blocked_by="- https://github.com/jeff/widgets/issues/13\n- #14")

    assert tickets(client) == [
        (13, "Export one table to CSV", "open", []),
        (14, "Export every table", "open", [13]),
        (15, "Escape awkward values", "open", [13, 14]),
    ]
    assert facts(client, "to_tickets")["tickets"][0]["url"] == "https://github.com/jeff/widgets/issues/13"


def test_once_polled_the_tickets_take_githubs_titles_and_native_blocking_edges(client, specced, github, clock):
    typed(client, "to-tickets", f"#{SPEC}")
    create_ticket(client, 13, "Export one table")
    create_ticket(client, 14, "Export every table")
    github.issues["jeff/widgets"] += [
        issue(13, "Export one table to CSV", parent=SPEC),
        issue(14, "Export every table", parent=SPEC),
    ]
    github.block("jeff/widgets", 14, 13)
    clock.advance(60)
    poll(client)

    assert tickets(client) == [(13, "Export one table to CSV", "open", []), (14, "Export every table", "open", [13])]


def test_a_to_tickets_session_is_done_on_stop(client, specced):
    typed(client, "to-tickets", f"#{SPEC}")
    create_ticket(client, 13, "Export one table to CSV")
    hook(client, "Stop", last_assistant_message="Tickets published.", background_tasks=[])

    assert session(client)["state"] == "Done"


def test_only_planning_sessions_of_each_kind_are_listed(client, tracked):
    tool(client, "WebSearch", {"query": "anything"}, response={})
    gh(client, 'gh issue create --title "A bug" --body "Broken."', stdout="https://github.com/jeff/widgets/issues/20\n")

    assert (state(client)["research"], state(client)["to_spec"], state(client)["to_tickets"]) == ([], [], [])
