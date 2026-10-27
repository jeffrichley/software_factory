"""The skill table: which role each skill plays, read from an editable, versioned TOML file.

A skill that is not in the table plays no role: its session stays ad hoc, labelled with the skill.
"""

import logging
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

from .work_items import Kind

log = logging.getLogger("factory_server")

DEFAULT_SKILL_TABLE = Path(__file__).resolve().parent / "tables" / "skills.toml"
TABLE_VERSION = 1  # the table format this server reads
MATT = "mattpocock-skills"
AD_HOC = "ad hoc"  # the kind of a session running no skill that sets one
JOB_ROLES = {"Ticket Job", "Spec Job"}
ROLES = JOB_ROLES | {"planning", "Phase signal"}
RANGE_CLAUSE = re.compile(r"\s*(>=|<=|==|>|<)\s*(\d+(?:\.\d+)*)\s*")


@dataclass(frozen=True)
class SkillRole:
    role: str
    # The session kind the skill gives: its Job role, its planning kind, or None for a Phase signal.
    kind: str | None
    # The kinds of Work item the skill is meant for; started against another kind, it is a Mismatch.
    work_items: tuple[Kind, ...] = ()


@dataclass(frozen=True)
class Entry:
    name: str
    role: SkillRole
    mattpocock_skills: str | None


def bare_name(skill: str) -> str | None:
    """The name a skill has in the table: Matt's skills with or without their plugin prefix; None for another plugin's."""
    plugin, _, name = skill.rpartition(":")
    return name if plugin in ("", MATT) else None


def skill_invocation(event: dict) -> tuple[str, str | None] | None:
    """The skill an event starts and its args: typed as `/<skill>` (UserPromptExpansion) or invoked by the model
    (PreToolUse(Skill))."""
    match event.get("hook_event_name"):
        case "UserPromptExpansion" if event.get("expansion_type", "slash_command") == "slash_command":
            skill, args = event.get("command_name"), event.get("command_args")
        case "PreToolUse" if event.get("tool_name") == "Skill":
            tool_input = event.get("tool_input") or {}
            skill, args = tool_input.get("skill"), tool_input.get("args")
        case _:
            return None
    return (skill, args) if skill else None


def work_item_named(args: str | None, repo: str) -> int | None:
    """The Work item a skill's args name: `#N`, a leading bare `N`, or an issue URL in the session's own repo."""
    issue_ref = re.compile(rf"(?:^|\s)#(\d+)\b|^\s*(\d+)\b|github\.com/{re.escape(repo)}/issues/(\d+)\b")
    m = issue_ref.search(args or "")
    return int(m[1] or m[2] or m[3]) if m else None


def version_key(version: str, width: int) -> tuple[int, ...]:
    parts = [int(n) for n in re.findall(r"\d+", version)]
    return tuple(parts + [0] * (width - len(parts)))


def check_range(spec: str) -> None:
    """`spec` is comma-separated comparisons, such as ">=1.4, <2"."""
    if not all(RANGE_CLAUSE.fullmatch(clause) for clause in spec.split(",")):
        raise ValueError(f"bad mattpocock_skills range {spec!r}")


def in_range(version: str | None, spec: str | None) -> bool:
    """No spec matches any version, even an unknown one; a spec never matches an unknown version."""
    if not spec:
        return True
    if version is None:
        return False
    ops = {">=": tuple.__ge__, "<=": tuple.__le__, ">": tuple.__gt__, "<": tuple.__lt__, "==": tuple.__eq__}
    for clause in spec.split(","):
        op, want = RANGE_CLAUSE.fullmatch(clause).groups()
        width = max(len(want.split(".")), len(version.split(".")))
        if not ops[op](version_key(version, width), version_key(want, width)):
            return False
    return True


def parse_table(text: str) -> list[Entry]:
    """The whole table, validated; raises ValueError (or TOMLDecodeError) naming what is wrong."""
    table = tomllib.loads(text)
    if table.get("version") != TABLE_VERSION:
        raise ValueError(f"unsupported table version {table.get('version')!r}; this server reads version {TABLE_VERSION}"
                         if "version" in table else f"missing version = {TABLE_VERSION}")
    entries = []
    for entry in table.get("skill", []):
        name, role, kind = entry.get("name"), entry.get("role"), entry.get("kind")
        if not isinstance(name, str) or not name:
            raise ValueError(f"an entry has no name: {entry!r}")
        if role not in ROLES:
            raise ValueError(f"{name}: unknown role {role!r}; use one of {sorted(ROLES)}")
        if (role == "planning") != isinstance(kind, str):
            raise ValueError(f"{name}: a planning skill needs a kind, and only a planning skill has one")
        if spec := entry.get("mattpocock_skills"):
            check_range(spec)
        work_items = entry.get("work_items", [])
        if not isinstance(work_items, list) or not set(work_items) <= set(get_args(Kind)):
            raise ValueError(f"{name}: work_items must list kinds of Work item, from {list(get_args(Kind))}")
        # The one place a role becomes a session kind.
        session_kind = {"planning": kind, "Phase signal": None}.get(role, role)
        entries.append(Entry(name, SkillRole(role, session_kind, tuple(work_items)), spec))
    return entries


class SkillTable:
    """Re-read on every lookup, so edits apply without restarting the server. A table that fails to load or
    validate is logged and the last good one kept; with no good table yet, every skill is unknown."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.text: str | None = None
        self.entries: list[Entry] = []

    def load(self) -> list[Entry]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError as e:
            log.error("skill table %s unreadable, keeping the last good table: %s", self.path, e)
            return self.entries
        if text != self.text:
            self.text = text  # a broken table is reported once, not on every skill start
            try:
                self.entries = parse_table(text)
            except (ValueError, tomllib.TOMLDecodeError) as e:
                log.error("skill table %s rejected, keeping the last good table: %s", self.path, e)
        return self.entries

    def role(self, name: str, mattpocock_skills_version: str | None) -> SkillRole | None:
        """The first entry for this table name whose version range holds; None when the skill is unknown."""
        for entry in self.load():
            if entry.name == name and in_range(mattpocock_skills_version, entry.mattpocock_skills):
                return entry.role
        return None
