"""Jobs: what a typed `/implement` registers, what it is told at start, and when its PR makes it Done."""

import re

# The Job roles the skill table gives.
TICKET_JOB = "Ticket Job"
SPEC_JOB = "Spec Job"

# Job stages; Merged, Closed and Abandoned come with the Job's end, and move it to History.
IN_PROGRESS = "In progress"
PR_OPEN = "PR open"
MERGED = "Merged"
CLOSED = "Closed"
ABANDONED = "Abandoned"
ENDED = (MERGED, CLOSED, ABANDONED)

# The words GitHub reads as closing an issue from a PR body.
CLOSING = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+#(\d+)\b", re.IGNORECASE)
SLUG_WORDS = 6
# A subagent saying which Ticket it works: `factory step --ticket N` (in any order with --job).
STEP_REPORT = re.compile(r"\bfactory(?:\.cmd)?\s+step\b.*?--ticket[\s=]+(\d+)")


def tickets_named(text: str, repo: str) -> list[int]:
    """The issue numbers a launch prompt or description names, in order: `#N` or an issue URL in the repo."""
    ref = re.compile(rf"(?<![\w&])#(\d+)\b|github\.com/{re.escape(repo)}/issues/(\d+)\b")
    return [int(m[1] or m[2]) for m in ref.finditer(text)]


# `git [-C <dir>] merge [options] <refs>`: where it ran, and what it merged.
GIT_MERGE = re.compile(r"\bgit\s+(?:-C\s+(\S+)\s+)?merge(?![-\w])([^;&|]*)")


def merge_of(command: str, cwd: str | None) -> tuple[str | None, list[str]] | None:
    """A `git merge` command's working directory (its -C, else the cwd) and the refs it merges; None if it isn't one."""
    m = GIT_MERGE.search(command)
    if not m:
        return None
    where = m[1].strip("'\"") if m[1] else cwd
    if where and cwd and not where.startswith(("/", "\\")) and not re.match(r"[A-Za-z]:", where):
        where = f"{cwd.rstrip('/')}/{where}"
    return where, [t for t in m[2].split() if not t.startswith("-")]


def is_agent_worktree(worktree: str | None) -> bool:
    """An isolated subagent's own worktree (`.claude/worktrees/agent-<agentId>`), on a branch of its own."""
    return bool(worktree and re.search(r"/\.claude/worktrees/agent-[^/]+$", worktree))


def spec_step_start(job_id: str) -> str:
    """The context injected into a Spec Job's subagent the Factory couldn't tie to a Ticket from its launch."""
    return (f"The Factory tracks Spec Job {job_id}. If you are implementing or merging one of its Tickets, first run "
            f"`factory step --ticket N --job {job_id}`, N being that Ticket's issue number.")


def closed_by(body: str | None) -> list[int]:
    """The issues a PR body closes when merged."""
    return sorted({int(n) for n in CLOSING.findall(body or "")})


def stage_of(pr: dict | None, abandoned: bool, item_state: str | None) -> str:
    """A Job's stage from its PR (with the PR's state), whether the human abandoned it, and its Work item's state.

    The human abandoning a Job is final. Otherwise its PR decides; a Work item closed with no
    non-draft PR abandons the Job. No timeouts.
    """
    if abandoned:
        return ABANDONED
    if pr and pr["state"] == "merged":
        return MERGED
    if pr and pr["state"] == "closed":
        return CLOSED
    if item_state == "closed" and (pr is None or pr["draft"]):
        return ABANDONED
    return PR_OPEN if pr and not pr["draft"] else IN_PROGRESS


def slug(title: str) -> str:
    """A title as a short kebab-case slug: "Add the widget API!" → add-the-widget-api."""
    return "-".join(re.findall(r"[a-z0-9]+", title.lower())[:SLUG_WORDS])


def worktree_of(cwd: str | None, main_tree: str) -> str | None:
    """The linked worktree a session works in, from its cwd; None in the main working tree (or unknown)."""
    if not cwd:
        return None
    path, main = cwd.replace("\\", "/").rstrip("/"), main_tree.replace("\\", "/").rstrip("/")
    m = re.match(r"(.*?/\.claude/worktrees/[^/]+)", path)
    if m:
        return m[1]
    if path == main or path.startswith(main + "/"):
        return None
    return path




def ticket_job_start(job_id: str, number: int | None, title: str | None, worktree: str | None,
                     duplicate_of: str | None = None) -> str:
    """The context injected when a Ticket Job starts: how to work it so that it ends as a PR the Factory can see."""
    n = str(number) if number else "<N>"
    lines = job_start(TICKET_JOB, job_id, number, title, worktree, duplicate_of)
    lines.append(f"3. When finished, push your branch, open a non-draft PR whose body closes the Ticket "
                 f"(`Closes #{n}`), then run `factory report pr <url> --job {job_id}`.")
    lines.append(escalate_line(job_id))
    return "\n".join(lines)


def spec_job_start(job_id: str, number: int | None, title: str | None, worktree: str | None,
                   duplicate_of: str | None = None) -> str:
    """The context injected when a Spec Job starts: its worktree's branch is the integration branch, and
    implement-spec works each Ticket in worktrees of its own."""
    n = str(number) if number else "<N>"
    lines = job_start(SPEC_JOB, job_id, number, title, worktree, duplicate_of)
    lines.append("3. implement-spec: use the current branch (this worktree's) as the integration branch; do not "
                 "create another one.")
    lines.append(f"4. When finished, push the integration branch. The PR's body closes the Spec and its Tickets "
                 f"(`Closes #{n}`, and `Closes #N` for each Ticket). Once the PR is non-draft (ready for review), "
                 f"run `factory report pr <url> --job {job_id}`.")
    lines.append(escalate_line(job_id))
    return "\n".join(lines)


def escalate_line(job_id: str) -> str:
    return f'Before you stop to ask for approval or help, run `factory escalate --job {job_id} "<reason>"`.'


def job_start(kind: str, job_id: str, number: int | None, title: str | None, worktree: str | None,
              duplicate_of: str | None = None) -> list[str]:
    """What every Job is told first: which Job it is, and the worktree to work in."""
    item, prefix = ("Spec", "spec") if kind == SPEC_JOB else ("Ticket", "ticket")
    n = str(number) if number else "<N>"
    name = f"{prefix}-{n}-{slug(title)}" if number and title else f"{prefix}-{n}-<slug>"
    lines = [f"The Factory tracks this as {kind} {job_id}" + (f" on #{number}." if number else ".")]
    if duplicate_of:
        lines.append(f"Note: Job {duplicate_of} is already working #{n}, so the Factory flags this Job as a duplicate. "
                     "It is not blocked: carry on unless the human says otherwise.")
    if not number:
        lines.append(f"It couldn't tell which {item} this is: once you know its issue number N, run "
                     f"`factory job --issue N --job {job_id}`.")
    lines.append("1. Run `git fetch` first.")
    if worktree:
        lines.append(f"2. You are already in a worktree ({worktree}): work there.")
    else:
        hint = "" if number and title else f", <slug> being a few words of the {item}'s title in kebab-case"
        lines.append(f"2. Use EnterWorktree named `{name}`{hint}, unless you are already in a worktree other than "
                     "the main one, and work there.")
    return lines
