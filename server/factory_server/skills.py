"""The skill table: which role each skill plays, read from an editable, versioned TOML file.

A skill that is not in the table plays no role: its session stays ad hoc, labelled with the skill.
"""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SKILL_TABLE = Path(__file__).resolve().parent / "tables" / "skills.toml"
MATT = "mattpocock-skills"
ROLES = {"Ticket Job", "Spec Job", "planning", "Phase signal"}


@dataclass(frozen=True)
class SkillRole:
    role: str
    # The session kind the skill gives: "Ticket Job", "Spec Job", a planning kind, or None (Phase signal).
    kind: str | None


def bare_name(skill: str) -> str | None:
    """The name a skill has in the table: Matt's skills with or without their plugin prefix; None for another plugin's."""
    plugin, _, name = skill.rpartition(":")
    return name if plugin in ("", MATT) else None


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", version))


def in_range(version: str | None, spec: str | None) -> bool:
    """`spec` is comma-separated comparisons, such as ">=1.4, <2"; no spec matches any version, even unknown."""
    if not spec:
        return True
    if version is None:
        return False
    ops = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
           "<": lambda a, b: a < b, "==": lambda a, b: a == b}
    for clause in spec.split(","):
        m = re.fullmatch(r"\s*(>=|<=|==|>|<)\s*([\d.]+)\s*", clause)
        if not m:
            raise ValueError(f"skill table: bad mattpocock_skills range {spec!r}")
        want = version_key(m[2])
        have = version_key(version)
        width = max(len(want), len(have))
        if not ops[m[1]](have + (0,) * (width - len(have)), want + (0,) * (width - len(want))):
            return False
    return True


class SkillTable:
    """Read on every lookup, so edits to the file apply without restarting the server."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def role(self, skill: str, mattpocock_skills_version: str | None) -> SkillRole | None:
        """The first entry for this skill whose version range holds; None when the skill is unknown."""
        name = bare_name(skill)
        if name is None:
            return None
        table = tomllib.loads(self.path.read_text(encoding="utf-8"))
        for entry in table.get("skill", []):
            if entry["name"] == name and in_range(mattpocock_skills_version, entry.get("mattpocock_skills")):
                role = entry["role"]
                if role not in ROLES or (role == "planning" and not entry.get("kind")):
                    raise ValueError(f"skill table: {name} needs a known role (and a kind when planning)")
                return SkillRole(role, {"planning": entry.get("kind"), "Phase signal": None}.get(role, role))
        return None
