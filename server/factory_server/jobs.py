"""Jobs: what a typed `/implement` registers, what it is told at start, and when its PR makes it Done."""

import re

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
    name = f"ticket-{n}-{slug(title)}" if number and title else f"ticket-{n}-<slug>"
    lines = [f"The Factory tracks this as Ticket Job {job_id}" + (f" on #{number}." if number else ".")]
    if duplicate_of:
        lines.append(f"Note: Job {duplicate_of} is already working #{n}, so the Factory flags this Job as a duplicate. "
                     "It is not blocked: carry on unless the human says otherwise.")
    if not number:
        lines.append(f"It couldn't tell which Ticket this is: once you know its issue number N, run "
                     f"`factory job --issue N --job {job_id}`.")
    lines.append("1. Run `git fetch` first.")
    if worktree:
        lines.append(f"2. You are already in a worktree ({worktree}): work there.")
    else:
        hint = "" if number and title else ", <slug> being a few words of the Ticket's title in kebab-case"
        lines.append(f"2. Use EnterWorktree named `{name}`{hint}, unless you are already in a worktree other than "
                     "the main one, and work there.")
    lines.append(f"3. When finished, push your branch, open a non-draft PR whose body closes the Ticket "
                 f"(`Closes #{n}`), then run `factory report pr <url> --job {job_id}`.")
    lines.append(f'Before you stop to ask for approval or help, run `factory escalate --job {job_id} "<reason>"`.')
    return "\n".join(lines)
