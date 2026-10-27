"""Step detail: what a Step's agent did, read from the same hook events as its Phase (test runs, edits, commits,
the agent's checklist, code-review's summary), and when it looks stuck."""

import re

# A test runner's summary counts, searched in the run's output.
PASSED = re.compile(r"\b(\d+)\s+(?:passed|passing)\b", re.IGNORECASE)
FAILED = re.compile(r"\b(\d+)\s+(?:failed|failing)\b", re.IGNORECASE)
# What `git commit` prints: `[<branch> (root-commit)? <sha>] <message>`, then its diffstat.
COMMIT_LINE = re.compile(r"^\[[^\]\n]*?\s([0-9a-f]{7,40})\]\s(.*)$", re.MULTILINE)
# What a fast-forward `git merge` prints: `Updating <old>..<new>`; a merge commit's SHA isn't printed.
FAST_FORWARD = re.compile(r"^Updating [0-9a-f]{7,40}\.\.([0-9a-f]{7,40})$", re.MULTILINE)
DIFFSTAT = re.compile(r"(\d+) files? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?")
# code-review's closing summary gives the findings per axis in no fixed format; read best-effort.
FINDINGS = r"(?:findings?|issues?)"
REVIEW_AXES = ("standards", "spec")
# The skill whose run the Factory asks the agent to report findings for (its table name).
CODE_REVIEW = "code-review"
# Struggle: this many failing test runs in a row; this many edits to one file since the tests last passed;
# this long without an event from a Step whose session is Working.
FAIL_STREAK = 3
CHURN_EDITS = 5
SILENCE_S = 10 * 60
# The test pulse shows the last few runs.
KEEP_RUNS = 12


def tool_response(event: dict) -> dict:
    """What the tool returned, as PostToolUse reports it; empty when the event carries none (or not as an object)."""
    response = event.get("tool_response")
    return response if isinstance(response, dict) else {}


def test_output(event: dict) -> str:
    """A test run's output: what it printed, or the error text a failed run comes with."""
    response = tool_response(event)
    return f"{response.get('stdout', '')}\n{response.get('stderr', '')}\n{event.get('error', '')}"


def test_counts(output: str) -> tuple[int | None, int | None]:
    """(passed, failed) from the runner's summary line; both None when it has none, a missing one 0."""
    passed, failed = PASSED.findall(output), FAILED.findall(output)
    if not passed and not failed:
        return None, None
    # The summary comes last; earlier matches may be per-file lines.
    return (int(passed[-1]) if passed else 0), (int(failed[-1]) if failed else 0)


def repo_relative(path: str, *trees: str | None) -> str:
    """A file's path inside the first of `trees` (worktree, then main tree) that holds it; else as given."""
    path = path.replace("\\", "/")
    for tree in trees:
        root = (tree or "").replace("\\", "/").rstrip("/")
        if root and path.startswith(root + "/"):
            return path[len(root) + 1:]
    return path


def lines_changed(event: dict) -> tuple[int, int] | None:
    """(added, deleted) lines of an Edit, MultiEdit or Write, from the structuredPatch Claude Code reports in
    tool_response (a new file's patch may be empty: then its content's lines); None when there is none to read."""
    response = tool_response(event)
    patch = response.get("structuredPatch")
    if not isinstance(patch, list):
        return None
    if not patch and response.get("type") == "create" and isinstance(response.get("content"), str):
        return len(response["content"].splitlines()), 0
    lines = [line for hunk in patch if isinstance(hunk, dict) for line in hunk.get("lines") or [] if isinstance(line, str)]
    return sum(line.startswith("+") for line in lines), sum(line.startswith("-") for line in lines)


def commit_made(event: dict) -> dict | None:
    """The commit a successful `git commit` made, from what it printed; None when it printed nothing to read."""
    response = tool_response(event)
    out = str(response.get("stdout") or "")
    head = COMMIT_LINE.search(out)
    if not head:
        return None
    stat = DIFFSTAT.search(out, head.end())
    files, added, deleted = (int(n or 0) for n in stat.groups()) if stat else (0, 0, 0)
    return {"sha": head[1], "message": head[2].strip(), "files": files, "added": added, "deleted": deleted}


def merge_sha(event: dict) -> str | None:
    """The commit a `git merge` left its branch on, when it printed it (a fast-forward does); else None."""
    response = tool_response(event)
    m = FAST_FORWARD.search(str(response.get("stdout") or ""))
    return m[1] if m else None


def axis_count(text: str, axis: str) -> int | None:
    """The findings code-review's summary gives one axis: "Standards: 3 findings", "2 on Standards", "Spec: no findings"."""
    for pattern in (rf"\b(\d+|no|zero)\s+(?:{FINDINGS}\s+)?(?:on|in|for)\s+(?:the\s+)?{axis}\b",
                    rf"\b{axis}\b\W{{0,12}}(\d+|no|zero|none)\b(?:\s+{FINDINGS})?"):
        if m := re.search(pattern, text, re.IGNORECASE):
            return int(m[1]) if m[1].isdigit() else 0
    return None


def review_counts(text: str) -> tuple[int, int] | None:
    """(standards, spec) findings from code-review's summary line, when both axes can be read."""
    standards, spec = (axis_count(text, axis) for axis in REVIEW_AXES)
    return None if standards is None or spec is None else (standards, spec)


def review_report_ask(job_id: str, ticket: int | None) -> str:
    """The context injected when a Job's agent starts code-review: report the findings count when done."""
    step = f" --ticket {ticket}" if ticket is not None else ""
    return (f"When the review is done, after its summary, run `factory review --standards N --spec M --job {job_id}{step}`, "
            "N and M being the number of findings on the Standards and Spec axes, so the Factory can show them.")


def checklist_after(items: list[dict] | None, event: dict) -> list[dict] | None:
    """The agent's checklist after the event, from TodoWrite's whole list or the Task tools' one task at a time;
    None when the event doesn't touch it. Items made by a task keep its id under "task"."""
    name, tool = event.get("hook_event_name"), event.get("tool_name")
    items = list(items or [])
    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    response = tool_response(event)
    if name == "PostToolUse" and tool == "TodoWrite":
        todos = response.get("newTodos", tool_input.get("todos"))
        if not isinstance(todos, list):
            return None
        tasks = [i for i in items if "task" in i]
        return [{"text": str(t.get("content", "")), "status": str(t.get("status", "pending"))}
                for t in todos if isinstance(t, dict)] + tasks
    if name == "TaskCreated" and event.get("task_id") is not None:
        task = str(event["task_id"])
        return [i for i in items if i.get("task") != task] + [
            {"text": str(event.get("task_subject") or ""), "status": "pending", "task": task}]
    if name == "TaskCompleted":
        return set_task_status(items, event.get("task_id"), "completed")
    if name == "PostToolUse" and tool == "TaskUpdate":
        status = tool_input.get("status") or (response.get("statusChange") or {}).get("to")
        if status == "deleted":
            return [i for i in items if i.get("task") != str(tool_input.get("taskId"))]
        return set_task_status(items, tool_input.get("taskId"), status, tool_input.get("subject"))
    return None


def set_task_status(items: list[dict], task: object, status: object, subject: object = None) -> list[dict] | None:
    if task is None or not (status or subject):
        return None
    return [{**i, **({"status": str(status)} if status else {}), **({"text": str(subject)} if subject else {})}
            if i.get("task") == str(task) else i for i in items]


def struggle_of(results: list[str], churned: list[str], silent_for_s: int | None) -> dict | None:
    """The struggle badge's reasons, from the Step's test results (oldest first), the files it keeps editing without
    a passing run, and how long it has been silent while Working; None when it isn't struggling."""
    streak = len(results) - next((i + 1 for i in reversed(range(len(results))) if results[i] != "fail"), 0)
    failures = streak if streak >= FAIL_STREAK else None
    silent = silent_for_s if silent_for_s is not None and silent_for_s >= SILENCE_S else None
    if failures is None and not churned and silent is None:
        return None
    return {"failures": failures, "churn": churned, "silent_for_s": silent}
