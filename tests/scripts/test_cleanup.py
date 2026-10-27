"""Seam 2: `factory cleanup` removes finished Jobs' worktrees and branches, only when the human asks."""

import subprocess
from pathlib import Path

from conftest import FACTORY, UV, git
from test_self_reports import installed


def cleanup(env, cwd: Path, answer: str | None = None, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [UV, "run", "--quiet", "--script", str(FACTORY), "cleanup", *args],
        cwd=cwd, env=env, input=answer or "", capture_output=True, text=True, timeout=120,
    )


def worktree(repo: Path, tmp_path: Path, branch: str) -> Path:
    """A Job's worktree on its own branch, as EnterWorktree makes it."""
    wt = tmp_path / branch
    git(repo, "worktree", "add", "-q", "-b", branch, str(wt))
    return wt


def job(job_id: str, number: int, wt: Path | None, branch: str | None, stage: str, machine: str = "wsl",
        repo: str = "jeff/widgets") -> dict:
    return {
        "id": job_id, "session_id": "7", "machine": machine, "kind": "Ticket Job", "repo": repo, "number": number,
        "work_item": {"title": f"Ticket {number}", "url": f"https://github.com/jeff/widgets/issues/{number}"},
        "worktree": wt and str(wt), "branch": branch, "stage": stage, "pr": None,
        "started_at": "2026-10-26T12:00:00Z", "duplicate_of": None,
    }


def branches(repo: Path) -> list[str]:
    return git(repo, "branch", "--format=%(refname:short)").splitlines()


def test_cleanup_lists_a_merged_jobs_worktree_and_removes_it_with_its_branch_when_asked(env, repo, server, tmp_path):
    installed(env, repo, server)
    wt = worktree(repo, tmp_path, "ticket-5-widget-api")
    server.state = {"jobs": [job("3", 5, wt, "ticket-5-widget-api", "Merged")]}

    done = cleanup(env, repo, "y\n")

    assert done.returncode == 0, done.stderr
    assert "#5" in done.stdout and str(wt) in done.stdout and "Merged" in done.stdout
    assert not wt.exists()
    assert branches(repo) == ["main"]


def test_cleanup_removes_nothing_unless_the_human_says_yes(env, repo, server, tmp_path):
    installed(env, repo, server)
    wt = worktree(repo, tmp_path, "ticket-5-widget-api")
    server.state = {"jobs": [job("3", 5, wt, "ticket-5-widget-api", "Closed")]}

    done = cleanup(env, repo, "n\n")

    assert done.returncode == 0, done.stderr
    assert "#5" in done.stdout
    assert wt.exists()
    assert "ticket-5-widget-api" in branches(repo)


def test_cleanup_never_touches_active_jobs_other_machines_or_other_repos(env, repo, server, tmp_path):
    installed(env, repo, server)
    working = worktree(repo, tmp_path, "ticket-6-in-progress")
    open_pr = worktree(repo, tmp_path, "ticket-7-pr-open")
    reworked = worktree(repo, tmp_path, "ticket-8-reworked")
    elsewhere = worktree(repo, tmp_path, "ticket-9-other-machine")
    other_repo = worktree(repo, tmp_path, "ticket-10-other-repo")
    server.state = {"jobs": [
        job("1", 6, working, "ticket-6-in-progress", "In progress"),
        job("2", 7, open_pr, "ticket-7-pr-open", "PR open"),
        # An ended Job whose worktree a later, active Job reuses.
        job("3", 8, reworked, "ticket-8-reworked", "Abandoned"),
        job("4", 8, reworked, None, "In progress"),
        job("5", 9, elsewhere, "ticket-9-other-machine", "Merged", machine="mac"),
        job("6", 10, other_repo, "ticket-10-other-repo", "Merged", repo="jeff/gadgets"),
    ]}

    done = cleanup(env, repo, "y\n")

    assert done.returncode == 0, done.stderr
    assert "No ended Job" in done.stdout
    assert all(wt.exists() for wt in (working, open_pr, reworked, elsewhere, other_repo))
    assert len(branches(repo)) == 6


def test_cleanup_refuses_a_worktree_with_uncommitted_changes_and_removes_the_rest(env, repo, server, tmp_path):
    installed(env, repo, server)
    dirty = worktree(repo, tmp_path, "ticket-5-dirty")
    (dirty / "notes.txt").write_text("not committed\n")
    clean = worktree(repo, tmp_path, "ticket-6-clean")
    server.state = {"jobs": [job("1", 5, dirty, "ticket-5-dirty", "Merged"), job("2", 6, clean, "ticket-6-clean", "Merged")]}

    done = cleanup(env, repo, "y\n")

    assert done.returncode != 0
    assert "uncommitted" in done.stdout + done.stderr and str(dirty) in done.stdout + done.stderr
    assert (dirty / "notes.txt").exists()
    assert "ticket-5-dirty" in branches(repo)
    assert not clean.exists()
    assert "ticket-6-clean" not in branches(repo)


def test_cleanup_removes_a_branch_left_after_its_worktree_went(env, repo, server, tmp_path):
    installed(env, repo, server)
    wt = worktree(repo, tmp_path, "ticket-5-widget-api")
    git(repo, "worktree", "remove", str(wt))
    server.state = {"jobs": [job("3", 5, wt, "ticket-5-widget-api", "Abandoned")]}

    done = cleanup(env, repo, None, "--yes")

    assert done.returncode == 0, done.stderr
    assert branches(repo) == ["main"]


def test_cleanup_refuses_when_the_server_is_unreachable(env, repo, server, tmp_path):
    installed(env, repo, server)
    wt = worktree(repo, tmp_path, "ticket-5-widget-api")
    server.close()

    done = cleanup(env, repo, "y\n")

    assert done.returncode != 0
    assert "unreachable" in done.stderr
    assert wt.exists()
