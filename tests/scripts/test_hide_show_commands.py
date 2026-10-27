"""Seam 2: 'factory hide' / 'factory show' report on the session that runs them, black-box."""

import json

from conftest import run_factory, run_hook
from test_tracking import event, set_up_machine


def tracked(env, repo, server):
    set_up_machine(env, repo, server.url)
    run_factory(env, repo, "install")


def test_factory_hide_and_show_report_the_session_that_runs_them(env, repo, server):
    tracked(env, repo, server)
    run_hook(env, event(repo, session="cc-old"))
    # The slash command runs 'factory hide' through the session's Bash tool, so its hook fires last.
    run_hook(env, event(repo, "PreToolUse", session="cc-1", tool_name="Bash"))

    hidden = run_factory(env, repo, "hide")
    shown = run_factory(env, repo, "show")

    assert hidden.returncode == 0, hidden.stderr
    assert shown.returncode == 0, shown.stderr
    hide, show = (r["body"] for r in server.received[-2:])
    assert hide["event"] == {"hook_event_name": "session_hidden", "session_id": "cc-1"}
    assert show["event"] == {"hook_event_name": "session_shown", "session_id": "cc-1"}
    assert (hide["machine"], hide["repo"]) == ("wsl", "jeff/widgets")
    assert hide["ids"] == {"session_id": "7", "job_id": None}


def test_factory_hide_queues_when_the_server_is_down(env, repo, server):
    tracked(env, repo, server)
    run_hook(env, event(repo))
    server.close()

    done = run_factory(env, repo, "hide")

    assert done.returncode == 0, done.stderr
    queue = (repo / ".factory" / "machines" / "wsl" / "queue.jsonl").read_text().splitlines()
    assert json.loads(queue[-1])["event"]["hook_event_name"] == "session_hidden"


def test_factory_hide_refuses_in_an_untracked_repo(env, repo, server):
    set_up_machine(env, repo, server.url)

    done = run_factory(env, repo, "hide")

    assert done.returncode != 0
    assert "factory install" in done.stdout + done.stderr
    assert server.received == []


def test_factory_hide_refuses_before_any_session_has_reported(env, repo, server):
    tracked(env, repo, server)

    done = run_factory(env, repo, "hide")

    assert done.returncode != 0
    assert "no session" in (done.stdout + done.stderr).lower()
