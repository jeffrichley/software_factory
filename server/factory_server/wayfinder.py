"""Wayfinder sessions: the Decision ticket a session works, inferred from its `gh` commands; its grilling rounds'
question titles, from assistant text; and its Map, read from the Map issue's body and its child Decision tickets."""

import re
import shlex

WAYFINDER = "Wayfinder"  # the session kind the skill table gives `wayfinder`
MAP_LABEL = "wayfinder:map"
TYPE_LABEL = "wayfinder:"

# Each Decision ticket type is worked with the human (HITL) or by the agent alone (AFK); a task may be either.
MODES = {"research": "AFK", "prototype": "HITL", "grilling": "HITL", "task": "HITL/AFK"}
# A stop on a ticket of these modes may be waiting on the human.
WAITS_ON_HUMAN = {"HITL", "HITL/AFK"}

# grilling's fixed round format: `❓ **Q1** - **<title>**: <body>`.
QUESTION = re.compile(r"❓\s*\*\*Q(\d+)\*\*\s*-\s*\*\*(.+?)\*\*:")
# Where one shell command ends and the next begins.
COMMAND_SEP = re.compile(r"&&|\|\||[;|\n]")
SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def mode_of(type_: str | None) -> str | None:
    return MODES.get(type_ or "")


def type_of(labels: list[str]) -> str | None:
    """A Decision ticket's type, from its `wayfinder:<type>` label."""
    return next((name[len(TYPE_LABEL):] for name in labels if name.startswith(TYPE_LABEL) and name != MAP_LABEL), None)


def questions(text: str | None) -> list[str]:
    """A grilling round's question titles, as `❓ Qn - <title>`, in order."""
    return [f"❓ Q{n} - {title.strip()}" for n, title in QUESTION.findall(text or "")]


def issue_number(arg: str, repo: str) -> int | None:
    m = re.fullmatch(rf"#?(\d+)|https?://github\.com/{re.escape(repo)}/issues/(\d+)/?", arg)
    return int(m[1] or m[2]) if m else None


def gh_issue_commands(command: str, repo: str) -> list[tuple[str, int | None, list[str]]]:
    """Each `gh issue edit|close|create` in a shell command: (action, the issue it names, its arguments)."""
    found = []
    for part in COMMAND_SEP.split(command or ""):
        try:
            words = shlex.split(part)
        except ValueError:
            words = part.split()
        for i in range(len(words) - 2):
            if words[i] in ("gh", "gh.exe") and words[i + 1] == "issue" and words[i + 2] in ("edit", "close", "create"):
                args = words[i + 3:]
                number = next((n for a in args if (n := issue_number(a, repo)) is not None), None)
                found.append((words[i + 2], number, args))
                break
    return found


def claims(command: str, repo: str) -> list[int]:
    """The tickets a command claims: `gh issue edit N --add-assignee …`."""
    return [n for action, n, args in gh_issue_commands(command, repo)
            if action == "edit" and n is not None and any(a.startswith("--add-assignee") for a in args)]


def closes(command: str, repo: str) -> list[int]:
    return [n for action, n, _ in gh_issue_commands(command, repo) if action == "close" and n is not None]


def creates(command: str, repo: str) -> list[bool]:
    """For each `gh issue create` in a command: does it create a Map (`--label wayfinder:map`)."""
    return [any(MAP_LABEL in a for a in args) for action, _, args in gh_issue_commands(command, repo) if action == "create"]


def created_numbers(stdout: str | None, repo: str) -> list[int]:
    """The issues `gh issue create` printed the URLs of."""
    return [int(n) for n in re.findall(rf"github\.com/{re.escape(repo)}/issues/(\d+)", stdout or "")]


def sections(body: str | None) -> dict[str, str]:
    """A Map body's `## ` sections by heading, with HTML comments dropped."""
    text = COMMENT.sub("", body or "")
    marks = list(SECTION.finditer(text))
    return {m[1]: text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)].strip()
            for i, m in enumerate(marks)}


def bullets(text: str) -> list[str]:
    """A section's list items, or its paragraphs when it has none."""
    items = [m[1].strip() for m in re.finditer(r"^\s*[-*]\s+(.+)$", text, re.MULTILINE)]
    return items or [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def linked(line: str, repo: str) -> int | None:
    m = re.search(rf"github\.com/{re.escape(repo)}/issues/(\d+)|(?<![\w&])#(\d+)\b", line)
    return int(m[1] or m[2]) if m else None


def map_of(body: str | None, repo: str) -> dict:
    """What a Map's body says: its Destination, its fog (Not yet specified), the gist of each decision so far by
    ticket number, and the tickets ruled out of scope."""
    s = sections(body)
    gists: dict[int, str] = {}
    for line in bullets(s.get("Decisions so far", "")):
        m = re.match(r"\[[^\]]*\]\([^)]*\)\s*:?\s*(.*)$", line)
        if (n := linked(line, repo)) is not None:
            gists[n] = m[1].strip() if m else line
    out = [n for line in bullets(s.get("Out of scope", "")) if (n := linked(line, repo)) is not None]
    return {"destination": s.get("Destination") or None, "fog": bullets(s.get("Not yet specified", "")),
            "gists": gists, "out_of_scope": out}
