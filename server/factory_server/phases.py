"""Phase rules: where a Step is in its work, inferred from hook signals by an editable, versioned TOML table.

An event gives at most one signal (a test run that failed, a source file edited, a skill started, …); the first
rule for that signal whose `from` holds the Step's Phase moves it to the rule's `to`. A signal no rule takes
leaves the Phase as it is; a Step no signal has reached shows "Phase unknown".
"""

import logging
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .skills import bare_name, check_range, in_range, skill_invocation
from .step_detail import tool_response

log = logging.getLogger("factory_server")

DEFAULT_PHASE_RULES = Path(__file__).resolve().parent / "tables" / "phases.toml"
TABLE_VERSION = 1  # the table format this server reads
PHASES = ("Exploring", "Red", "Green", "Refactor", "Reviewing", "Committed", "Merged")
UNKNOWN = "unknown"  # how a rule's `from` names a Step whose Phase is unknown
PENDING = "Pending"  # a Spec Job's Step no subagent has started on yet; before the Phases, never inferred
ANY = "*"
SIGNALS = {"explore", "test_edit", "source_edit", "test_pass", "test_fail", "commit", "merge", "pr_merged"}
SKILL_SIGNAL = "skill:"  # skill:<name>, a skill started in the Step (a Phase signal such as tdd or code-review)
PATTERN_LISTS = ("test_files", "test_commands", "failed_summary", "commit_commands", "merge_commands")
TOOL_LISTS = ("explore_tools", "edit_tools")
# The patterns a repo's [repos."owner/repo"] section can add to, for test runners and layouts of its own.
REPO_PATTERN_LISTS = ("test_files", "test_commands", "failed_summary")


@dataclass(frozen=True)
class Rule:
    on: str
    from_: frozenset[str]
    to: str
    job_kinds: frozenset[str] = frozenset()  # empty = every kind of Job
    mattpocock_skills: str | None = None


@dataclass(frozen=True)
class Rules:
    rules: tuple[Rule, ...] = ()
    tools: dict[str, frozenset[str]] = field(default_factory=dict)
    patterns: dict[str, tuple[re.Pattern, ...]] = field(default_factory=dict)
    # Each repo's own patterns, added to the shared ones for events in that repo.
    repo_patterns: dict[str, dict[str, tuple[re.Pattern, ...]]] = field(default_factory=dict)

    def matches(self, name: str, text: str, repo: str | None = None) -> bool:
        own = self.repo_patterns.get(repo, {}).get(name, ()) if repo else ()
        return any(p.search(text) for p in (*self.patterns.get(name, ()), *own))

    def signal(self, event: dict, repo: str | None = None) -> str | None:
        """What the event (in `repo`) says about the Step's work, if anything."""
        if invocation := skill_invocation(event):
            name = bare_name(invocation[0])
            return f"{SKILL_SIGNAL}{name}" if name else None
        name, tool = event.get("hook_event_name"), event.get("tool_name")
        if name not in ("PostToolUse", "PostToolUseFailure"):
            return None
        tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
        failed = name == "PostToolUseFailure"
        if tool in self.tools.get("edit_tools", ()):
            if failed:
                return None
            path = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "").replace("\\", "/")
            return "test_edit" if self.matches("test_files", path, repo) else "source_edit"
        if tool == "Bash":
            return self.bash_signal(event, str(tool_input.get("command") or ""), failed, tool_input, repo)
        if tool in self.tools.get("explore_tools", ()) and not failed:
            return "explore"
        return None

    def bash_signal(self, event: dict, command: str, failed: bool, tool_input: dict, repo: str | None) -> str | None:
        if self.matches("test_commands", command, repo):
            if tool_input.get("run_in_background") or event.get("is_interrupt"):
                return None  # the outcome isn't known
            if failed:
                return "test_fail" if str(event.get("error", "")).startswith("Exit code") else None
            # A piped run exits with the last command's status: its output's summary line decides.
            response = tool_response(event)
            output = f"{response.get('stdout', '')}\n{response.get('stderr', '')}"
            return "test_fail" if self.matches("failed_summary", output, repo) else "test_pass"
        if failed:
            return None
        if self.matches("commit_commands", command):
            return "commit"
        if self.matches("merge_commands", command):
            return "merge"
        return "explore"

    def next_phase(self, phase: str | None, signal: str, job_kind: str | None, mattpocock_skills_version: str | None) -> str | None:
        """The Phase after `signal`; None when no rule takes it."""
        current = phase or UNKNOWN
        for rule in self.rules:
            if (rule.on == signal and (ANY in rule.from_ or current in rule.from_)
                    and (not rule.job_kinds or job_kind in rule.job_kinds)
                    and in_range(mattpocock_skills_version, rule.mattpocock_skills)):
                return rule.to
        return None


def phase_named(name: str) -> str | None:
    """A Phase from how a human or agent typed it ("red", "Green"); None when it isn't one."""
    return next((p for p in PHASES if p.lower() == name.strip().lower()), None)


def parse_rules(text: str) -> Rules:
    """The whole table, validated; raises ValueError (or TOMLDecodeError) naming what is wrong."""
    table = tomllib.loads(text)
    if table.get("version") != TABLE_VERSION:
        raise ValueError(f"unsupported table version {table.get('version')!r}; this server reads version {TABLE_VERSION}"
                         if "version" in table else f"missing version = {TABLE_VERSION}")
    signals = table.get("signals", {})
    tools, patterns = {}, {}
    for name in TOOL_LISTS:
        tools[name] = frozenset(strings(signals, name))
    for name in PATTERN_LISTS:
        patterns[name] = compiled(signals, name, f"signals.{name}")
    repos = table.get("repos", {})
    if not isinstance(repos, dict):
        raise ValueError('repos must be a table of [repos."owner/repo"] sections')
    repo_patterns = {}
    for repo, section in repos.items():
        if not isinstance(section, dict) or not set(section) <= set(REPO_PATTERN_LISTS):
            raise ValueError(f'repos."{repo}" may only list {", ".join(REPO_PATTERN_LISTS)}')
        repo_patterns[repo] = {name: compiled(section, name, f'repos."{repo}".{name}') for name in REPO_PATTERN_LISTS}
    rules = []
    for rule in table.get("rule", []):
        on, to = rule.get("on"), rule.get("to")
        if not isinstance(on, str) or not (on in SIGNALS or (on.startswith(SKILL_SIGNAL) and len(on) > len(SKILL_SIGNAL))):
            raise ValueError(f"a rule has an unknown signal {on!r}; use one of {sorted(SIGNALS)} or skill:<name>")
        if to not in PHASES:
            raise ValueError(f"rule on {on}: unknown Phase {to!r}; use one of {list(PHASES)}")
        from_ = strings(rule, "from")
        if not from_ or not set(from_) <= {*PHASES, UNKNOWN, ANY}:
            raise ValueError(f"rule on {on}: `from` must list Phases, {UNKNOWN!r} or {ANY!r}")
        if spec := rule.get("mattpocock_skills"):
            check_range(spec)
        rules.append(Rule(on, frozenset(from_), to, frozenset(strings(rule, "job_kinds")), spec))
    return Rules(tuple(rules), tools, patterns, repo_patterns)


def compiled(table: dict, key: str, where: str) -> tuple[re.Pattern, ...]:
    try:
        return tuple(re.compile(p) for p in strings(table, key))
    except re.error as e:
        raise ValueError(f"{where}: bad pattern: {e}") from None


def strings(table: dict, key: str) -> list[str]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"{key} must be a list of strings")
    return value


class PhaseRules:
    """Re-read on every use, so edits apply without restarting the server. A table that fails to load or
    validate is logged and the last good one kept; with no good table yet, no signal moves a Phase."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.text: str | None = None
        self.rules = Rules()

    def load(self) -> Rules:
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError as e:
            log.error("Phase rules %s unreadable, keeping the last good rules: %s", self.path, e)
            return self.rules
        if text != self.text:
            self.text = text  # a broken table is reported once, not on every event
            try:
                self.rules = parse_rules(text)
            except (ValueError, tomllib.TOMLDecodeError) as e:
                log.error("Phase rules %s rejected, keeping the last good rules: %s", self.path, e)
        return self.rules
