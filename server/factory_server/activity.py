"""A session's "now: …" headline, from what its latest event shows it doing."""

import re
from pathlib import PurePosixPath, PureWindowsPath

LONGEST = 120
# A command up to this long reads as it is ("running cargo test"); a longer one is said in fewer words.
COMMAND_SHORT = 60
# Kept in full beside the headline (the dashboard shows it on hover), up to this long.
DETAIL_LONGEST = 4000

CD_FIRST = re.compile(r"^cd\s+(?:\"[^\"]*\"|'[^']*'|\S+)\s*(?:&&|;)\s*")
TITLE = re.compile(r"""(?:--title|-t)[\s=]+(?:"([^"]*)"|'([^']*)'|(\S+))""")
CREATES = (("gh issue create", "creating issue"), ("gh pr create", "opening PR"))


def short(text: str) -> str:
    line = text.strip().splitlines()[0] if text.strip() else ""
    return line if len(line) <= LONGEST else line[: LONGEST - 1] + "…"


def rel(path: str, cwd: str | None) -> str:
    """A path relative to the session's working directory when it lies inside it."""
    flavour = PureWindowsPath if "\\" in path or ":" in path[:2] else PurePosixPath
    if cwd:
        try:
            return str(flavour(path).relative_to(flavour(cwd))).replace("\\", "/")
        except ValueError:
            pass
    return path


def running_skill(skill: str) -> str:
    """A skill the skill table doesn't know."""
    return f"running skill `{skill}`"


def started_skill(name: str) -> str:
    """A skill the skill table knows (a Job, a planning kind or a Phase signal)."""
    return f"started `{name}`"


def cut(line: str, longest: int) -> str:
    return line if len(line) <= longest else line[: longest - 1] + "…"


def command_headline(command: str, description: str | None) -> str:
    """A shell command in a few words, as variant E's "now:" reads: a short one as it is (any `cd` first left out),
    a new issue or PR by its title, else the description Claude gave it, else its first line cut short."""
    command = command.strip()
    while m := CD_FIRST.match(command):
        command = command[m.end():]
    first, *more = command.splitlines() or [""]
    if not more and len(first) <= COMMAND_SHORT:
        return f"running {first}"
    for prefix, says in CREATES:
        if first.startswith(prefix) and (t := TITLE.search(first)):
            return f'{says} "{cut(next(g for g in t.groups() if g is not None), COMMAND_SHORT)}"'
    if description and description.strip():
        d = cut(description.strip().splitlines()[0], COMMAND_SHORT)
        return d[0].lower() + d[1:] if len(d) < 2 or not d[1].isupper() else d
    return f"running {cut(first, COMMAND_SHORT)}" + (" …" if more and len(first) <= COMMAND_SHORT else "")


def tool_detail(event: dict) -> str | None:
    """What a PreToolUse event's headline leaves out, shown in full on hover: a shell command as it was run."""
    args = event.get("tool_input") or {}
    if event.get("tool_name") in ("Bash", "PowerShell") and args.get("command"):
        return cut(str(args["command"]), DETAIL_LONGEST)
    return None


def tool_headline(event: dict) -> str:
    """What a PreToolUse event shows the session doing."""
    tool = event.get("tool_name") or "a tool"
    args = event.get("tool_input") or {}
    cwd = event.get("cwd")
    match tool:
        case "Read" if "file_path" in args:
            return f"reading {rel(args['file_path'], cwd)}"
        case "Edit" | "MultiEdit" | "Write" if "file_path" in args:
            return f"editing {rel(args['file_path'], cwd)}"
        case "NotebookEdit" if "notebook_path" in args:
            return f"editing {rel(args['notebook_path'], cwd)}"
        case "Bash" | "PowerShell" if args.get("command"):
            return command_headline(str(args["command"]), args.get("description"))
        case "Grep" if "pattern" in args:
            return f"searching for \"{short(args['pattern'])}\""
        case "Glob" if "pattern" in args:
            return f"finding {short(args['pattern'])}"
        case "WebFetch" if "url" in args:
            return f"fetching {short(args['url'])}"
        case "WebSearch" if "query" in args:
            return f"searching the web for \"{short(args['query'])}\""
        case "Agent" | "Task" if args.get("description"):
            return f"running subagent: {short(args['description'])}"
    return f"using {tool}"
