"""Planning sessions other than Wayfinder: what a research, to-spec or to-tickets session has done so far, read from
its tool calls (never from transcripts).

- research: its question (the skill's args), the searches run, the sources fetched and its findings file.
- to-spec: the Map it came from, which sections of the Spec template it has written, and the Spec it published.
- to-tickets: its Spec and the Tickets it created, with their blocking edges.
"""

import re

from .wayfinder import issue_number, sections

RESEARCH, TO_SPEC, TO_TICKETS = "research", "to-spec", "to-tickets"
KINDS = (RESEARCH, TO_SPEC, TO_TICKETS)

# The sections of to-spec's Spec template, in order.
SPEC_OUTLINE = ("Problem Statement", "Solution", "User Stories", "Implementation Decisions", "Testing Decisions",
                "Out of Scope", "Further Notes")
EDIT_TOOLS = ("Write", "Edit", "MultiEdit")
# The files a to-spec or to-tickets session wrote last, kept for a `gh issue create --body-file` that names one.
KEEP_FILES = 10
WORKTREE = re.compile(r"^.*?/\.claude/worktrees/[^/]+/")
CREATE = re.compile(r"\bgh(?:\.exe)?\s+issue\s+create\b")
HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def empty(kind: str) -> dict:
    """What a session of the kind knows before it has done anything."""
    return {
        RESEARCH: {"question": None, "searches": [], "sources": [], "findings": None},
        TO_SPEC: {"map": None, "spec": None, "written": []},
        TO_TICKETS: {"spec": None, "tickets": []},
    }[kind]


def repo_relative(path: str, repo_path: str) -> str | None:
    """A file's path inside the repo (from the main working tree or one of its worktrees); None outside it."""
    path, main = path.replace("\\", "/"), repo_path.replace("\\", "/").rstrip("/")
    if m := WORKTREE.match(path):
        return path[m.end():]
    if path.startswith(main + "/"):
        return path[len(main) + 1:]
    return None


def findings(path: str, repo: str, repo_path: str) -> dict:
    """The findings file, with its link on GitHub once pushed (only for a file inside the repo)."""
    rel = repo_relative(path, repo_path)
    return {"path": rel or path, "url": f"https://github.com/{repo}/blob/HEAD/{rel}" if rel else None}


def written_text(event: dict) -> tuple[str | None, str]:
    """A file an edit tool wrote: its path and the text it wrote."""
    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    texts = [tool_input.get("content"), tool_input.get("new_string"),
             *(e.get("new_string") for e in tool_input.get("edits") or [] if isinstance(e, dict))]
    return tool_input.get("file_path"), "\n".join(t for t in texts if isinstance(t, str))


def outline_sections(text: str) -> list[str]:
    """The Spec template's sections that a text has a heading for."""
    found = {h.strip().lower() for h in HEADING.findall(text or "")}
    return [s for s in SPEC_OUTLINE if s.lower() in found]


OPTION = r"(?<![\w-])(?:{names})(?:=|\s+)(?:\"((?:[^\"\\]|\\.)*)\"|'([^']*)'|(\S+))"


def option(command: str, *names: str) -> str | None:
    """An option's value in a shell command, quoted or bare."""
    m = re.search(OPTION.format(names="|".join(re.escape(n) for n in names)), command)
    return next((g for g in m.groups() if g is not None), None) if m else None


def created_issue(command: str, files: dict[str, str]) -> tuple[str | None, str] | None:
    """A command that creates exactly one issue: its title and body (inline, or from a file the session wrote)."""
    if len(CREATE.findall(command or "")) != 1:
        return None
    title = option(command, "--title", "-t")
    body_file = option(command, "--body-file", "-F")
    if body_file:
        name = body_file.replace("\\", "/")
        body = next((text for path, text in files.items() if path.replace("\\", "/").endswith(name.lstrip("./"))), "")
    else:
        body = command  # the body is inline, often a heredoc: the whole command holds it
    return title, body


def blocked_by(body: str, repo: str) -> list[int]:
    """The issues a ticket's body lists under `## Blocked by`."""
    text = sections(body).get("Blocked by", "")
    refs = re.findall(rf"github\.com/{re.escape(repo)}/issues/(\d+)|(?<![\w&])#(\d+)\b", text)
    return sorted({int(a or b) for a, b in refs})


def viewed(command: str, repo: str) -> list[int]:
    """The issues a command views: `gh issue view N`."""
    return [n for arg in re.findall(r"\bgh(?:\.exe)?\s+issue\s+view\s+(\S+)", command or "")
            if (n := issue_number(arg.strip("'\""), repo)) is not None]
