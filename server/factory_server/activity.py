"""A session's "now: …" headline, from what its latest event shows it doing."""

from pathlib import PurePosixPath, PureWindowsPath

LONGEST = 120


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
    return f"running skill `{skill}`"


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
            return f"running {short(args['command'])}"
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
        case "Skill" if args.get("skill"):
            return running_skill(args["skill"])
    return f"using {tool}"
