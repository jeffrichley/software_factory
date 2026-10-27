"""Seam 2: the `factory` self-reports a Job sends, black-box."""

from conftest import git, run_factory, run_hook
from test_tracking import event, set_up_machine

PR_URL = "https://github.com/jeff/widgets/pull/50"


def installed(env, repo, server) -> None:
    set_up_machine(env, repo, server.url)
    assert run_factory(env, repo, "install").returncode == 0


def test_report_pr_from_the_jobs_worktree_reaches_the_server(env, repo, server, tmp_path):
    installed(env, repo, server)
    wt = tmp_path / "widgets-ticket-5"
    git(repo, "worktree", "add", "-q", str(wt))

    done = run_factory(env, wt, "report", "pr", PR_URL, "--job", "3")

    assert done.returncode == 0, done.stderr
    body = server.received[-1]["body"]
    assert body["event"] == {"hook_event_name": "report_pr", "job_id": "3", "url": PR_URL}
    assert (body["machine"], body["repo"], body["repo_path"]) == ("wsl", "jeff/widgets", str(repo.resolve()))


def test_job_reports_the_jobs_work_item(env, repo, server):
    installed(env, repo, server)

    done = run_factory(env, repo, "job", "--issue", "5", "--job", "3")

    assert done.returncode == 0, done.stderr
    assert server.received[-1]["body"]["event"] == {"hook_event_name": "job_issue", "job_id": "3", "issue": 5}


def test_phase_reports_the_steps_phase(env, repo, server):
    installed(env, repo, server)

    done = run_factory(env, repo, "phase", "red", "--job", "3")
    assert done.returncode == 0, done.stderr
    assert server.received[-1]["body"]["event"] == {"hook_event_name": "report_phase", "job_id": "3", "phase": "Red"}

    done = run_factory(env, repo, "phase", "Committed", "--job", "3", "--ticket", "5")
    assert done.returncode == 0, done.stderr
    assert server.received[-1]["body"]["event"] == {
        "hook_event_name": "report_phase", "job_id": "3", "phase": "Committed", "ticket": 5,
    }


def test_phase_refuses_a_name_that_is_not_a_phase(env, repo, server):
    installed(env, repo, server)

    done = run_factory(env, repo, "phase", "testing", "--job", "3")

    assert done.returncode != 0
    assert "Exploring" in done.stdout + done.stderr
    assert server.events() == ["repo_installed"]


def test_every_self_report_requires_its_job(env, repo, server):
    installed(env, repo, server)

    for args in (("report", "pr", PR_URL), ("job", "--issue", "5"), ("phase", "red")):
        done = run_factory(env, repo, *args)
        assert done.returncode != 0
        assert "--job" in done.stdout + done.stderr
    assert server.events() == ["repo_installed"]


def test_a_self_report_with_the_server_down_is_queued_and_delivered_first_later(env, repo, server):
    installed(env, repo, server)
    server.close()

    done = run_factory(env, repo, "report", "pr", PR_URL, "--job", "3")
    assert done.returncode == 0, done.stderr

    server.restart()
    run_hook(env, event(repo, "Stop"))
    assert server.events() == ["repo_installed", "report_pr", "Stop"]


def test_a_self_report_from_an_untracked_repo_is_refused(env, repo, server):
    set_up_machine(env, repo, server.url)

    done = run_factory(env, repo, "report", "pr", PR_URL, "--job", "3")

    assert done.returncode != 0
    assert "factory install" in done.stdout + done.stderr
    assert server.received == []


def test_escalate_reports_why_the_job_needs_the_human(env, repo, server):
    installed(env, repo, server)

    done = run_factory(env, repo, "escalate", "--job", "3", "Which database should this use?")

    assert done.returncode == 0, done.stderr
    assert server.received[-1]["body"]["event"] == {
        "hook_event_name": "escalate", "job_id": "3", "reason": "Which database should this use?",
    }


def test_escalate_requires_its_job(env, repo, server):
    installed(env, repo, server)

    done = run_factory(env, repo, "escalate", "Which database?")

    assert done.returncode != 0
    assert "--job" in done.stdout + done.stderr
    assert server.events() == ["repo_installed"]
