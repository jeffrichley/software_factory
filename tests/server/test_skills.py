"""Seam 1: sessions classified by the skill they run, through the skill table."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from factory_server import create_app
from test_sessions import FakeGitHub, clock, client, hook_event  # noqa: F401 - fixtures


def typed(command: str, args: str = "", **over) -> dict:
    """The human typed `/<command> <args>`."""
    return hook_event(
        "UserPromptExpansion", expansion_type="slash_command", command_name=command, command_args=args,
        command_source="plugin", prompt=f"/{command} {args}".strip(), **over,
    )


def skill_call(skill: str, **over) -> dict:
    """The model invoked a skill with the Skill tool."""
    return hook_event("PreToolUse", tool_name="Skill", tool_input={"skill": skill}, tool_use_id="toolu_1", **over)


def start(version: str | None = "1.3.1", **over) -> dict:
    envelope = hook_event("SessionStart", source="startup", **over)
    return {**envelope, "mattpocock_skills_version": version}


def session(client) -> dict:
    [row] = client.get("/api/state").json()["sessions"]
    return row


def test_a_session_that_runs_no_skill_is_ad_hoc(client):
    client.post("/api/events", json=start())

    row = session(client)
    assert (row["kind"], row["skill"], row["now"], row["actions"]) == ("ad hoc", None, None, [])


@pytest.mark.parametrize(
    ("command", "kind"),
    [("implement", "Ticket Job"), ("implement-spec", "Spec Job"), ("wayfinder", "Wayfinder"),
     ("to-spec", "to-spec"), ("to-tickets", "to-tickets"), ("research", "research")],
)
def test_a_typed_skill_sets_the_sessions_kind(client, command, kind):
    client.post("/api/events", json=start())

    client.post("/api/events", json=typed(command, "#3"))

    row = session(client)
    assert (row["kind"], row["skill"]) == (kind, command)


def test_a_skill_the_model_invokes_sets_the_kind_too(client):
    client.post("/api/events", json=start())

    client.post("/api/events", json=skill_call("mattpocock-skills:wayfinder"))

    row = session(client)
    assert (row["kind"], row["skill"], row["now"]) == ("Wayfinder", "wayfinder", "running skill `wayfinder`")


def test_an_unknown_skill_shows_as_running_skill_in_an_ad_hoc_row(client):
    client.post("/api/events", json=start())

    client.post("/api/events", json=typed("deploy-preview"))

    row = session(client)
    assert (row["kind"], row["skill"], row["now"]) == ("ad hoc", "deploy-preview", "running skill `deploy-preview`")
    assert row["actions"] == [{"at": "2026-10-26T12:00:00Z", "text": "running skill `deploy-preview`"}]


def test_phase_signals_and_unknown_skills_inside_a_job_keep_its_kind(client):
    client.post("/api/events", json=start())
    client.post("/api/events", json=typed("implement", "#3"))

    client.post("/api/events", json=skill_call("mattpocock-skills:tdd"))
    client.post("/api/events", json=skill_call("diagnosing-bugs"))

    row = session(client)
    assert (row["kind"], row["skill"]) == ("Ticket Job", "implement")
    assert row["now"] == "running skill `diagnosing-bugs`"


def test_a_subagents_skill_does_not_reclassify_its_session(client):
    client.post("/api/events", json=start())
    client.post("/api/events", json=typed("implement-spec", "#18"))

    client.post("/api/events", json=skill_call("implement", agent_id="agent-1", agent_type="general-purpose"))

    assert session(client)["kind"] == "Spec Job"


def test_another_plugins_skill_of_the_same_name_is_not_matts(client):
    client.post("/api/events", json=start())

    client.post("/api/events", json=skill_call("acme:implement"))

    row = session(client)
    assert (row["kind"], row["skill"]) == ("ad hoc", "acme:implement")


def test_the_headline_and_timeline_follow_tool_activity(client, clock):
    client.post("/api/events", json=start())
    tools = [
        ("Read", {"file_path": "/home/jeff/widgets/src/render/chunk.ts"}, "reading src/render/chunk.ts"),
        ("Grep", {"pattern": "seamOffset", "path": "src/"}, "searching for \"seamOffset\""),
        ("Edit", {"file_path": "/home/jeff/widgets/src/a.ts", "old_string": "x", "new_string": "y"}, "editing src/a.ts"),
        ("Bash", {"command": "cargo test\n--quiet", "description": "Run tests"}, "running cargo test"),
        ("Write", {"file_path": "/tmp/elsewhere.txt", "content": ""}, "editing /tmp/elsewhere.txt"),
        ("WebFetch", {"url": "https://docs.github.com/rest", "prompt": "?"}, "fetching https://docs.github.com/rest"),
        ("Agent", {"description": "Explore the repo", "prompt": "..."}, "running subagent: Explore the repo"),
        ("mcp__thing__do", {}, "using mcp__thing__do"),
    ]
    for i, (tool, tool_input, _) in enumerate(tools):
        clock.advance(60)
        client.post("/api/events", json=hook_event("PreToolUse", tool_name=tool, tool_input=tool_input, tool_use_id=f"t{i}"))

    row = session(client)
    assert row["now"] == "using mcp__thing__do"
    assert [a["text"] for a in row["actions"]] == [expected for _, _, expected in tools]
    assert row["actions"][0]["at"] == "2026-10-26T12:01:00Z"

    clock.advance(60)
    client.post("/api/events", json=hook_event("PreToolUse", tool_name="Read", tool_input={"file_path": "/home/jeff/widgets/b.py"}))

    # The timeline keeps the last 8 actions, oldest first.
    actions = session(client)["actions"]
    assert len(actions) == 8
    assert (actions[0]["text"], actions[-1]["text"]) == ("searching for \"seamOffset\"", "reading b.py")


@pytest.fixture
def table_client(tmp_path, clock):
    """A server whose skill table is a file the test writes (and may edit while the server runs)."""
    table = tmp_path / "skills.toml"

    def make(text: str) -> TestClient:
        table.write_text(text)
        return TestClient(create_app(db_path=tmp_path / "f.db", github=FakeGitHub(), clock=clock, skill_table=table))

    make.table = table
    return make


def test_a_table_entry_can_apply_only_to_a_mattpocock_skills_version_range(table_client):
    client = table_client(
        "version = 1\n"
        "[[skill]]\nname = \"ship\"\nrole = \"Ticket Job\"\nmattpocock_skills = \">=1.4, <2\"\n"
        "[[skill]]\nname = \"ship\"\nrole = \"planning\"\nkind = \"research\"\n"
    )
    for session_id, version in [("old", "1.3.1"), ("new", "1.4.0"), ("next", "2.0.0"), ("unknown", None)]:
        client.post("/api/events", json=start(version, session=session_id))
        client.post("/api/events", json=typed("ship", session=session_id))

    kinds = [s["kind"] for s in client.get("/api/state").json()["sessions"]]
    assert kinds == ["research", "Ticket Job", "research", "research"]


def test_edits_to_the_skill_table_apply_without_a_restart(table_client):
    client = table_client("version = 1\n")
    client.post("/api/events", json=start(session="a"))
    client.post("/api/events", json=typed("ship", session="a"))

    table_client.table.write_text("version = 1\n[[skill]]\nname = \"ship\"\nrole = \"Spec Job\"\n")
    client.post("/api/events", json=start(session="b"))
    client.post("/api/events", json=typed("ship", session="b"))

    assert [s["kind"] for s in client.get("/api/state").json()["sessions"]] == ["ad hoc", "Spec Job"]


def test_a_database_from_before_the_skill_table_still_works(tmp_path, clock):
    db = tmp_path / "old.db"
    old = sqlite3.connect(db)
    old.executescript(
        "CREATE TABLE sessions (id INTEGER PRIMARY KEY, machine TEXT NOT NULL, repo TEXT NOT NULL,"
        " cc_session_id TEXT NOT NULL, state TEXT NOT NULL, state_since TEXT NOT NULL, ended_at TEXT,"
        " UNIQUE (machine, cc_session_id));"
        "INSERT INTO sessions (machine, repo, cc_session_id, state, state_since)"
        " VALUES (\"wsl\", \"jeff/widgets\", \"cc-1\", \"Working\", \"2026-10-26T11:00:00Z\");"
    )
    old.commit()
    old.close()
    client = TestClient(create_app(db_path=db, github=FakeGitHub(), clock=clock))

    client.post("/api/events", json=typed("implement", "#3"))

    row = session(client)
    assert (row["kind"], row["state_since"]) == ("Ticket Job", "2026-10-26T11:00:00Z")
