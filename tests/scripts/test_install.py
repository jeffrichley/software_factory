"""Seam 2: `factory install` / `uninstall` / `status` / `dashboard`, black-box."""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from conftest import configure_skills, git, run_factory


def set_up_machine(env, cwd, url, name="wsl"):
    done = run_factory(env, cwd, "setup", "--machine", name, "--server", url)
    assert done.returncode == 0, done.stderr


def output(done) -> str:
    return done.stdout + done.stderr


def test_install_announces_the_repo_to_the_server(env, repo, server):
    set_up_machine(env, repo, server.url)

    done = run_factory(env, repo, "install")

    assert done.returncode == 0, done.stderr
    [sent] = [r["body"] for r in server.received]
    assert sent["event"] == {"hook_event_name": "repo_installed"}
    assert (sent["machine"], sent["repo"], sent["repo_path"]) == ("wsl", "jeff/widgets", str(repo.resolve()))


def test_install_refuses_until_the_repo_is_configured_for_matts_skills(env, bare_repo, server):
    set_up_machine(env, bare_repo, server.url)

    done = run_factory(env, bare_repo, "install")

    assert done.returncode != 0
    assert "/setup-matt-pocock-skills" in output(done)
    assert not (bare_repo / ".factory").exists()
    assert server.received == []


def test_install_warns_when_the_config_is_not_on_origin_head(env, bare_repo, server):
    set_up_machine(env, bare_repo, server.url)
    configure_skills(bare_repo)  # committed, not pushed

    done = run_factory(env, bare_repo, "install")

    assert done.returncode == 0, done.stderr
    assert "origin/HEAD" in output(done)
    assert (bare_repo / ".factory" / "machines" / "wsl.json").exists()


def test_install_does_not_warn_when_the_config_is_on_origin_head(env, repo, server):
    set_up_machine(env, repo, server.url)

    assert "origin/HEAD" not in output(run_factory(env, repo, "install"))


def test_installing_again_changes_nothing_and_prints_status(env, repo, server):
    set_up_machine(env, repo, server.url)
    run_factory(env, repo, "install")
    marker = (repo / ".factory" / "machines" / "wsl.json").read_text()

    done = run_factory(env, repo, "install")

    assert done.returncode == 0, done.stderr
    assert (repo / ".factory" / "machines" / "wsl.json").read_text() == marker
    assert server.events() == ["repo_installed"]
    assert "Tracked on 'wsl'" in done.stdout
    assert "reachable" in done.stdout


def test_install_succeeds_with_the_server_down_and_queues_the_event(env, repo, server):
    set_up_machine(env, repo, server.url)
    server.close()

    done = run_factory(env, repo, "install")

    assert done.returncode == 0, done.stderr
    assert (repo / ".factory" / "machines" / "wsl.json").exists()
    assert "queued" in output(done)
    assert git(repo, "status", "--porcelain") == ""


def test_a_queued_install_is_delivered_before_the_uninstall(env, repo, server):
    set_up_machine(env, repo, server.url)
    server.close()
    run_factory(env, repo, "install")
    server.restart()

    done = run_factory(env, repo, "uninstall")

    assert done.returncode == 0, done.stderr
    assert server.events() == ["repo_installed", "repo_uninstalled"]


def test_a_half_written_queue_line_does_not_block_the_queue(env, repo, server):
    set_up_machine(env, repo, server.url)
    server.close()
    run_factory(env, repo, "install")
    with (repo / ".factory" / "machines" / "wsl" / "queue.jsonl").open("a") as f:
        f.write('{"machine": "ws\n')
    server.restart()

    done = run_factory(env, repo, "uninstall")

    assert done.returncode == 0, done.stderr
    assert server.events() == ["repo_installed", "repo_uninstalled"]


def fake_uv(tmp_path: Path, version: str) -> Path:
    """A `uv` that only reports its version, first on PATH."""
    d = tmp_path / "fake-uv"
    d.mkdir()
    if sys.platform == "win32":
        (d / "uv.cmd").write_text(f"@echo uv {version}\n")
    else:
        (d / "uv").write_text(f"#!/bin/sh\necho 'uv {version}'\n")
        (d / "uv").chmod(0o755)
    return d


def test_install_refuses_when_uv_is_too_old(env, repo, server, tmp_path):
    set_up_machine(env, repo, server.url)
    env["PATH"] = f"{fake_uv(tmp_path, '0.4.0')}{os.pathsep}{env['PATH']}"

    done = run_factory(env, repo, "install")

    assert done.returncode != 0
    assert "uv 0.4.0" in output(done)
    assert not (repo / ".factory").exists()


def test_install_refuses_when_uv_is_missing(env, repo, server):
    set_up_machine(env, repo, server.url)
    git_dir = str(Path(shutil.which("git")).parent)
    if shutil.which("uv", path=git_dir):
        pytest.skip("uv sits beside git, so it can't be hidden from PATH")
    env["PATH"] = git_dir

    done = run_factory(env, repo, "install")

    assert done.returncode != 0
    assert "uv" in output(done)
    assert not (repo / ".factory").exists()


def test_uninstall_removes_only_this_machines_tracking(env, repo, server, tmp_path):
    set_up_machine(env, repo, server.url, name="mac")
    run_factory(env, repo, "install")
    set_up_machine(env, repo, server.url, name="wsl")
    run_factory(env, repo, "install")
    (repo / ".factory" / "machines" / "wsl" / "sessions").mkdir(parents=True)
    wt = tmp_path / "widgets-ticket-3"
    git(repo, "worktree", "add", "-q", "-b", "ticket-3-x", str(wt))

    done = run_factory(env, repo, "uninstall")

    assert done.returncode == 0, done.stderr
    assert sorted(p.name for p in (repo / ".factory" / "machines").iterdir()) == ["mac.json"]
    assert (repo / ".factory" / ".gitignore").exists()
    assert (repo / "docs" / "agents" / "issue-tracker.md").exists()
    assert wt.exists()
    assert "ticket-3-x" in git(repo, "branch", "--list", "ticket-3-x")
    [sent] = [r["body"] for r in server.received if r["body"]["event"]["hook_event_name"] == "repo_uninstalled"]
    assert (sent["machine"], sent["repo"], sent["repo_path"]) == ("wsl", "jeff/widgets", str(repo.resolve()))


def test_uninstalling_the_last_machine_removes_factory_dir(env, repo, server):
    set_up_machine(env, repo, server.url)
    run_factory(env, repo, "install")

    done = run_factory(env, repo, "uninstall")

    assert done.returncode == 0, done.stderr
    assert not (repo / ".factory").exists()
    assert server.events() == ["repo_installed", "repo_uninstalled"]


def test_uninstall_still_removes_tracking_with_the_server_down(env, repo, server):
    set_up_machine(env, repo, server.url)
    run_factory(env, repo, "install")
    server.close()

    done = run_factory(env, repo, "uninstall")

    assert done.returncode == 0, done.stderr
    assert not (repo / ".factory").exists()
    assert "unreachable" in output(done)


def test_status_shows_tracking_reachability_and_current_ids(env, repo, server):
    set_up_machine(env, repo, server.url)
    run_factory(env, repo, "install")
    sessions = repo / ".factory" / "machines" / "wsl" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "cc-1.json").write_text(json.dumps({"session_id": "41", "job_id": "9"}))

    done = run_factory(env, repo, "status")

    assert done.returncode == 0, done.stderr
    assert "Tracked on 'wsl'" in done.stdout
    assert "Server reachable" in done.stdout
    assert "Latest session 41, Job 9" in done.stdout
    assert "origin/HEAD" not in done.stdout


def test_status_says_how_to_start_an_unreachable_server(env, repo, server):
    set_up_machine(env, repo, server.url)
    server.close()

    done = run_factory(env, repo, "status")

    assert done.returncode == 0, done.stderr
    assert "Not tracked on 'wsl'" in done.stdout
    assert "unreachable" in done.stdout
    assert "factory server" in done.stdout


def test_status_repeats_the_origin_head_warning(env, bare_repo, server):
    set_up_machine(env, bare_repo, server.url)
    configure_skills(bare_repo)
    run_factory(env, bare_repo, "install")

    assert "origin/HEAD" in run_factory(env, bare_repo, "status").stdout


def test_status_reports_an_old_uv(env, repo, server, tmp_path):
    set_up_machine(env, repo, server.url)
    env["PATH"] = f"{fake_uv(tmp_path, '0.4.0')}{os.pathsep}{env['PATH']}"

    assert "uv 0.4.0 is too old" in run_factory(env, repo, "status").stdout


def test_dashboard_says_how_to_start_an_unreachable_server(env, repo, server):
    set_up_machine(env, repo, server.url)
    server.close()

    done = run_factory(env, repo, "dashboard")

    assert done.returncode != 0
    assert "factory server" in output(done)


def test_setup_offers_a_shell_alias(env, repo, server):
    done = run_factory(env, repo, "setup", "--machine", "wsl", "--server", server.url)

    assert done.returncode == 0, done.stderr
    assert "alias factory" in done.stdout.lower()


@pytest.mark.skipif(sys.platform != "win32", reason="the .cmd shim is for PowerShell/cmd")
def test_factory_runs_from_cmd_through_its_shim(env, repo):
    import subprocess

    from conftest import ROOT

    done = subprocess.run(
        [str(ROOT / "bin" / "factory.cmd"), "--help"], cwd=repo, env=env, capture_output=True, text=True, timeout=120
    )

    assert done.returncode == 0, done.stderr
    assert "install" in done.stdout
