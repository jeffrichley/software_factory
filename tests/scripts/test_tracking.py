"""Seam 2: `factory setup` / `factory install` and the hook, black-box."""

import json
import socket
import time

from conftest import HOOKS_JSON, git, run_factory, run_hook


def set_up_machine(env, cwd, url, name="wsl"):
    done = run_factory(env, cwd, "setup", "--machine", name, "--server", url)
    assert done.returncode == 0, done.stderr


def event(repo, name="SessionStart", session="cc-1", **fields):
    return {"hook_event_name": name, "session_id": session, "cwd": str(repo), **fields}


def test_install_writes_only_a_git_ignored_per_machine_marker(env, repo, server):
    set_up_machine(env, repo, server.url)

    done = run_factory(env, repo, "install")

    assert done.returncode == 0, done.stderr
    assert (repo / ".factory" / ".gitignore").read_text().strip() == "*"
    marker = json.loads((repo / ".factory" / "machines" / "wsl.json").read_text())
    assert marker["factory_version"] == "0.1.0"
    assert marker["installed_at"]
    assert git(repo, "status", "--porcelain") == ""


def test_install_refuses_before_setup(env, repo):
    done = run_factory(env, repo, "install")

    assert done.returncode != 0
    assert "factory setup" in done.stdout + done.stderr
    assert not (repo / ".factory").exists()


def test_the_hook_reports_nothing_from_an_untracked_repo(env, repo, server):
    set_up_machine(env, repo, server.url)

    done = run_hook(env, event(repo))

    assert done.returncode == 0, done.stderr
    assert done.stdout == ""
    assert server.received == []


def test_the_hook_posts_each_event_stamped_and_sends_back_cached_ids(env, repo, server):
    set_up_machine(env, repo, server.url)
    run_factory(env, repo, "install")
    start = event(repo, source="startup")

    assert run_hook(env, start).returncode == 0
    assert run_hook(env, event(repo, "PreToolUse", tool_name="Bash")).returncode == 0

    installed, first, second = (r["body"] for r in server.received)
    assert installed["event"] == {"hook_event_name": "repo_installed"}
    assert server.received[1]["path"] == "/api/events"
    assert first["event"] == start
    assert first["machine"] == "wsl"
    assert first["repo"] == "jeff/widgets"
    assert first["repo_path"] == str(repo.resolve())
    assert first["mattpocock_skills_version"] == "1.3.1"
    assert first["ids"] == {}
    assert second["ids"] == {"session_id": "7", "job_id": None}
    assert "mattpocock_skills_version" not in second


def test_a_session_in_a_linked_worktree_reports_against_the_main_tree(env, repo, server, tmp_path):
    set_up_machine(env, repo, server.url)
    run_factory(env, repo, "install")
    wt = tmp_path / "widgets-ticket-3"
    git(repo, "worktree", "add", "-q", str(wt))

    assert run_hook(env, event(wt)).returncode == 0

    assert server.received[-1]["body"]["repo_path"] == str(repo.resolve())


def test_the_hook_passes_inject_back_as_additional_context(env, repo, server):
    set_up_machine(env, repo, server.url)
    run_factory(env, repo, "install")
    server.reply = {**server.reply, "inject": "Work in your own worktree."}

    done = run_hook(env, event(repo, "UserPromptExpansion", command_name="implement"))

    assert json.loads(done.stdout) == {
        "hookSpecificOutput": {"hookEventName": "UserPromptExpansion", "additionalContext": "Work in your own worktree."}
    }


def test_the_hook_exits_cleanly_when_the_server_is_down(env, repo, server):
    set_up_machine(env, repo, server.url)
    run_factory(env, repo, "install")
    server.close()

    done = run_hook(env, event(repo))

    assert done.returncode == 0
    assert done.stdout == ""


def test_install_refuses_a_repo_without_a_github_remote(env, repo, server):
    set_up_machine(env, repo, server.url)
    git(repo, "remote", "set-url", "origin", "https://gitlab.com/jeff/widgets.git")

    done = run_factory(env, repo, "install")

    assert done.returncode != 0
    assert "GitHub" in done.stdout + done.stderr
    assert not (repo / ".factory").exists()


def test_the_next_hook_event_delivers_a_queued_install_first(env, repo, server):
    set_up_machine(env, repo, server.url)
    server.close()
    run_factory(env, repo, "install")
    server.restart()

    assert run_hook(env, event(repo)).returncode == 0

    assert server.events() == ["repo_installed", "SessionStart"]


def test_with_the_server_down_the_hook_queues_each_event_with_its_cached_ids(env, repo, server):
    set_up_machine(env, repo, server.url)
    run_factory(env, repo, "install")
    run_hook(env, event(repo))
    server.close()
    server.received.clear()

    assert run_hook(env, event(repo, "PreToolUse", tool_name="Bash")).returncode == 0
    assert run_hook(env, event(repo, "Stop")).returncode == 0
    server.restart()
    assert run_hook(env, event(repo, "UserPromptSubmit")).returncode == 0

    assert server.events() == ["PreToolUse", "Stop", "UserPromptSubmit"]
    assert all(r["body"]["ids"] == {"session_id": "7", "job_id": None} for r in server.received)
    # Queued events carry when they happened, for the server to use instead of when they arrived.
    assert ["queued_at" in r["body"] for r in server.received] == [True, True, False]
    assert not (repo / ".factory" / "machines" / "wsl" / "queue.jsonl").exists()


def test_the_hook_exits_within_its_time_budget_when_the_server_never_answers(env, repo, server):
    set_up_machine(env, repo, server.url)
    run_factory(env, repo, "install")
    server.close()
    # Takes the connection but never replies: the slowest way for the server to be down.
    with socket.create_server(("127.0.0.1", int(server.url.rsplit(":", 1)[1]))):
        started = time.monotonic()
        done = run_hook(env, event(repo))
        elapsed = time.monotonic() - started

    budget = json.loads(HOOKS_JSON.read_text())["hooks"]["SessionStart"][0]["hooks"][0]["timeout"]
    assert done.returncode == 0
    assert elapsed < budget
    queue = (repo / ".factory" / "machines" / "wsl" / "queue.jsonl").read_text().splitlines()
    assert [json.loads(line)["event"]["hook_event_name"] for line in queue] == ["SessionStart"]


def test_an_event_the_server_refuses_is_dropped_and_never_blocks_the_queue(env, repo, server):
    set_up_machine(env, repo, server.url)
    server.close()
    run_factory(env, repo, "install")
    run_hook(env, event(repo))
    server.restart()
    server.refuse = {"repo_installed"}

    done = run_hook(env, event(repo, "PreToolUse", tool_name="Bash"))

    assert done.returncode == 0
    assert "refused" in done.stderr
    assert server.events() == ["repo_installed", "SessionStart", "PreToolUse"]
    assert not (repo / ".factory" / "machines" / "wsl" / "queue.jsonl").exists()


def test_a_slow_server_and_a_long_queue_cannot_make_the_hook_overrun(env, repo, server):
    set_up_machine(env, repo, server.url)
    run_factory(env, repo, "install")
    server.close()
    names = ["UserPromptSubmit", "PreToolUse", "PostToolUse", "PreToolUse", "PostToolUse", "Stop"]
    for name in names:
        run_hook(env, event(repo, name))
    server.restart()
    server.received.clear()
    server.delay = 1.0

    started = time.monotonic()
    done = run_hook(env, event(repo, "UserPromptSubmit"))
    elapsed = time.monotonic() - started

    budget = json.loads(HOOKS_JSON.read_text())["hooks"]["UserPromptSubmit"][0]["hooks"][0]["timeout"]
    assert done.returncode == 0
    assert elapsed < budget
    assert 0 < len(server.received) < len(names)
    server.delay = 0
    run_hook(env, event(repo, "Stop"))
    assert server.events() == [*names, "UserPromptSubmit", "Stop"]
