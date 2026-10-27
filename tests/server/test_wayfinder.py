"""Seam 1: a Wayfinder session, its Decision ticket, its HITL stops and its Map, through the Factory server's HTTP API."""

import pytest

from conftest import gh, hook, install, issue, poll

MAP = 1
MAP_BODY = """## Destination

A written Spec for the widget exporter.

## Notes

Use grilling.

## Decisions so far

<!-- the index -->

- [Survey the export formats](https://github.com/jeff/widgets/issues/2): CSV first, JSON later

## Not yet specified

<!-- fog -->

- Streaming very large exports
- Who may export

## Out of scope

- [Export to PDF](https://github.com/jeff/widgets/issues/7): PDF is a print feature, not an export
"""


def ticket(number: int, title: str, type_: str, state: str = "open", assignees: tuple[str, ...] = ()) -> dict:
    """A Decision ticket: a child of the Map with its `wayfinder:<type>` label."""
    return {**issue(number, title, labels=(f"wayfinder:{type_}",), parent=MAP, state=state),
            "assignees": [{"login": a} for a in assignees]}


@pytest.fixture
def chart(client, github):
    """Map #1 with Decision tickets: research #2 (closed), grilling #3, prototype #4, research #5, task #6,
    and #7 ruled out of scope. Tracked and polled."""
    github.issues["jeff/widgets"] = [
        issue(MAP, "Widgets: chart the way to a spec", labels=("wayfinder:map",), body=MAP_BODY),
        ticket(2, "Survey the export formats", "research", state="closed"),
        ticket(3, "Choose the export columns", "grilling"),
        ticket(4, "Prototype the export dialog", "prototype"),
        ticket(5, "Read the CSV RFC", "research"),
        ticket(6, "Provision a test bucket", "task"),
        ticket(7, "Export to PDF", "grilling", state="closed"),
    ]
    install(client)
    poll(client)


def wayfinder(client, args: str = f"#{MAP}", **over) -> dict:
    """The human typed `/wayfinder <args>`."""
    return hook(client, "UserPromptExpansion", expansion_type="slash_command", command_name="wayfinder",
                command_args=args, command_source="plugin", prompt=f"/wayfinder {args}".strip(), **over)


def state(client) -> dict:
    return client.get("/api/state").json()


def session(client) -> dict:
    [row] = state(client)["sessions"]
    return row


def planning(client) -> dict:
    """The Wayfinder session's planning facts."""
    [row] = state(client)["wayfinder"]
    return row


def test_the_decision_ticket_is_unknown_until_the_session_claims_one(client, chart):
    wayfinder(client)
    gh(client, f"gh issue view {MAP}")

    assert planning(client)["map"] == MAP
    assert planning(client)["ticket"] is None


def test_claiming_a_ticket_with_add_assignee_makes_it_the_decision_ticket_being_worked(client, chart):
    wayfinder(client)

    gh(client, "gh issue edit 3 --add-assignee @me")

    assert planning(client)["ticket"] == 3


def test_a_claim_may_name_the_ticket_by_url_and_put_the_assignee_first(client, chart):
    wayfinder(client, "https://github.com/jeff/widgets/issues/1")

    gh(client, "gh issue edit --add-assignee jeffrichley https://github.com/jeff/widgets/issues/4 && gh issue view 4")

    assert (planning(client)["map"], planning(client)["ticket"]) == (MAP, 4)


def test_closing_a_ticket_records_the_decision_and_names_the_ticket_when_no_claim_was_seen(client, chart):
    wayfinder(client)

    gh(client, 'gh issue comment 3 --body "Columns: id, name" && gh issue close 3')

    assert (planning(client)["ticket"], planning(client)["closed"]) == (3, [3])


def test_tickets_the_session_creates_are_read_from_gh_issue_creates_output(client, chart):
    wayfinder(client)
    gh(client, "gh issue edit 3 --add-assignee @me")

    gh(client, 'gh issue create --title "Choose the delimiter" --label wayfinder:grilling --body "## Question"',
       stdout="https://github.com/jeff/widgets/issues/8\n")

    assert (planning(client)["ticket"], planning(client)["created"]) == (3, [8])


def test_charting_a_new_map_makes_it_the_sessions_map(client, chart):
    wayfinder(client, "an exporter for widgets")
    assert planning(client)["map"] is None

    gh(client, 'gh issue create --title "Exporter: chart the way" --label "wayfinder:map" --body-file map.md',
       stdout="https://github.com/jeff/widgets/issues/9\n")
    gh(client, 'gh issue create --title "Survey formats" --label "wayfinder:research" --body "## Question"',
       stdout="https://github.com/jeff/widgets/issues/10\n")

    assert (planning(client)["map"], planning(client)["created"]) == (9, [10])


def test_a_subagents_claim_is_not_the_ticket_the_session_works(client, chart):
    wayfinder(client)
    gh(client, "gh issue edit 3 --add-assignee @me")

    gh(client, "gh issue edit 5 --add-assignee @me", agent_id="r1", agent_type="general-purpose")
    gh(client, "gh issue close 5", agent_id="r1", agent_type="general-purpose")

    assert (planning(client)["ticket"], planning(client)["closed"]) == (3, [5])


ROUND = ("Two questions on the columns.\n\n❓ **Q1** - **Column order**: id first?\n➡️ Yes\n\n---\n\n"
         "❓ **Q2** - **Empty values**: blank or null?\n➡️ Blank\n")


def test_stopping_on_a_hitl_ticket_needs_you_with_the_ticket_and_the_rounds_question_titles(client, chart):
    wayfinder(client)
    gh(client, "gh issue edit 3 --add-assignee @me")

    hook(client, "Stop", last_assistant_message=ROUND, background_tasks=[])

    row = session(client)
    assert (row["kind"], row["state"]) == ("Wayfinder", "Needs you")
    assert row["reason"] == {"kind": "hitl", "ticket": "#3 Choose the export columns",
                             "questions": ["❓ Q1 - Column order", "❓ Q2 - Empty values"]}
    assert planning(client)["questions"] == ["❓ Q1 - Column order", "❓ Q2 - Empty values"]


def test_the_rounds_titles_may_come_from_message_display_and_clear_once_answered(client, chart):
    wayfinder(client)
    gh(client, "gh issue edit 4 --add-assignee @me")
    hook(client, "MessageDisplay", delta=ROUND)

    hook(client, "Stop", last_assistant_message="Over to you.", background_tasks=[])
    assert session(client)["reason"]["questions"] == ["❓ Q1 - Column order", "❓ Q2 - Empty values"]

    hook(client, "UserPromptSubmit", prompt="Yes, and blank.")
    assert (session(client)["state"], planning(client)["questions"]) == ("Working", [])


def test_stopping_on_an_afk_ticket_is_done(client, chart):
    wayfinder(client)
    gh(client, "gh issue edit 5 --add-assignee @me")

    hook(client, "Stop", last_assistant_message="Research recorded.", background_tasks=[])

    assert session(client)["state"] == "Done"


def test_stopping_after_closing_the_hitl_ticket_is_done(client, chart):
    wayfinder(client)
    gh(client, "gh issue edit 3 --add-assignee @me")
    gh(client, "gh issue close 3")

    hook(client, "Stop", last_assistant_message="Decision recorded on the Map.", background_tasks=[])

    assert session(client)["state"] == "Done"


def test_with_no_ticket_claimed_a_stop_needs_you_only_on_a_grilling_round(client, chart):
    wayfinder(client, "an exporter for widgets")
    hook(client, "Stop", last_assistant_message="What should the map reach?", background_tasks=[])
    assert session(client)["state"] == "Done"

    hook(client, "UserPromptSubmit", prompt="A spec.")
    hook(client, "Stop", last_assistant_message=ROUND, background_tasks=[])
    assert session(client)["reason"] == {"kind": "hitl", "ticket": "Decision ticket unknown",
                                         "questions": ["❓ Q1 - Column order", "❓ Q2 - Empty values"]}


def test_a_hitl_stop_sounds_after_the_grace(client, chart, clock):
    wayfinder(client)
    gh(client, "gh issue edit 3 --add-assignee @me")
    hook(client, "Stop", last_assistant_message=ROUND, background_tasks=[])

    clock.advance(10)
    assert [s["sound"] for s in state(client)["sounds"]] == ["needs_you"]


def test_the_map_has_its_destination_fog_and_decision_tickets_without_those_out_of_scope(client, chart, github, clock):
    github.issues["jeff/widgets"][2]["assignees"] = [{"login": "jeffrichley"}]
    clock.advance(60)
    poll(client)

    [m] = state(client)["maps"]
    assert (m["number"], m["title"], m["destination"]) == (MAP, "Widgets: chart the way to a spec",
                                                           "A written Spec for the widget exporter.")
    assert m["fog"] == ["Streaming very large exports", "Who may export"]
    assert [(t["number"], t["type"], t["mode"], t["state"], t["assignees"], t["gist"]) for t in m["tickets"]] == [
        (2, "research", "AFK", "closed", [], "CSV first, JSON later"),
        (3, "grilling", "HITL", "open", ["jeffrichley"], None),
        (4, "prototype", "HITL", "open", [], None),
        (5, "research", "AFK", "open", [], None),
        (6, "task", "HITL/AFK", "open", [], None),
    ]


def test_only_wayfinder_sessions_are_listed_with_planning_facts(client, chart):
    hook(client, "PreToolUse", tool_name="Bash", tool_use_id="t1", tool_input={"command": "gh issue edit 3 --add-assignee @me"})

    assert state(client)["wayfinder"] == []
