"""Step detail: what a Step's agent did, read from the same hook events as its Phase (test runs, edits, commits,
the agent's checklist, code-review's summary), and when it looks stuck."""

import re

# A test runner's summary counts, searched in the run's output.
PASSED = re.compile(r"\b(\d+)\s+(?:passed|passing)\b", re.IGNORECASE)
FAILED = re.compile(r"\b(\d+)\s+(?:failed|failing)\b", re.IGNORECASE)
# What `git commit` prints: `[<branch> (root-commit)? <sha>] <message>`, then its diffstat.
COMMIT_LINE = re.compile(r"^\[[^\]\n]*?\s([0-9a-f]{7,40})\]\s(.*)$", re.MULTILINE)
DIFFSTAT = re.compile(r"(\d+) files? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?")
# code-review's closing summary gives the findings per axis in no fixed format; read best-effort.
FINDINGS = r"(?:findings?|issues?)"
REVIEW_AXES = ("standards", "spec")
# The skill whose run the Factory asks the agent to report findings for (its table name).
CODE_REVIEW = "code-review"
# The test pulse shows the last few runs.
KEEP_RUNS = 12


def test_output(event: dict) -> str:
    """A test run's output: what it printed, or the error text a failed run comes with."""
    response = event.get("tool_response") if isinstance(event.get("tool_response"), dict) else {}
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


def commit_made(event: dict) -> dict | None:
    """The commit a successful `git commit` made, from what it printed; None when it printed nothing to read."""
    response = event.get("tool_response") if isinstance(event.get("tool_response"), dict) else {}
    out = str(response.get("stdout") or "")
    head = COMMIT_LINE.search(out)
    if not head:
        return None
    stat = DIFFSTAT.search(out, head.end())
    files, added, deleted = (int(n or 0) for n in stat.groups()) if stat else (0, 0, 0)
    return {"sha": head[1], "message": head[2].strip(), "files": files, "added": added, "deleted": deleted}


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
