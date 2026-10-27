"""Work items: a Tracked repo's issues that have a kind, taken from GitHub structure alone (never from the skill)."""

import re
from typing import Literal

Kind = Literal["Map", "Decision ticket", "Spec", "Ticket"]
MAP: Kind = "Map"
DECISION_TICKET: Kind = "Decision ticket"
SPEC: Kind = "Spec"
TICKET: Kind = "Ticket"

MAP_LABEL = "wayfinder:map"
# A child names its parent in its body where sub-issues aren't available: a `Part of #N` line (wayfinder) or a
# `## Parent` section (to-tickets).
BODY_PARENT = re.compile(r"^(?:Part of #(\d+)|## Parent\s+#(\d+))", re.MULTILINE)
# The sections every to-spec Spec opens with.
SPEC_SECTIONS = ("## Problem Statement", "## Solution")


def work_items(repo: str, issues: list[dict]) -> list[dict]:
    """The repo's Work items: its issues (PRs left out) that are a Map, Decision ticket, Spec or Ticket."""
    by_number = {i["number"]: i for i in issues if "pull_request" not in i}
    known: dict[int, Kind | None] = {}

    def kind(number: int, seen: frozenset[int] = frozenset()) -> Kind | None:
        if number not in known:
            known[number] = derive(number, seen | {number})
        return known[number]

    def derive(number: int, seen: frozenset[int]) -> Kind | None:
        issue = by_number[number]
        names = {label["name"] for label in issue.get("labels", [])}
        if MAP_LABEL in names:
            return MAP
        if any(name.startswith("wayfinder:") for name in names):
            return DECISION_TICKET  # wayfinder labels each Map child with its type
        parent = parent_of(repo, issue)
        parent_kind = kind(parent, seen) if parent in by_number and parent not in seen else None
        if parent_kind == SPEC:
            return TICKET
        if parent_kind == MAP:
            return DECISION_TICKET
        body = issue.get("body") or ""
        if all(section in body for section in SPEC_SECTIONS):
            return SPEC
        if parent is None and (issue.get("sub_issues_summary") or {}).get("total"):
            return SPEC  # to-tickets split it into Tickets
        return None

    rows = [
        {"number": n, "title": i["title"], "state": i["state"], "url": i["html_url"], "kind": kind(n)}
        for n, i in by_number.items()
    ]
    return [row for row in rows if row["kind"]]


def pull_requests(issues: list[dict]) -> list[dict]:
    """The repo's PRs, each open, closed or merged, and whether it is a draft."""
    return [
        {
            "number": i["number"],
            "title": i["title"],
            "state": "merged" if i["pull_request"].get("merged_at") else i["state"],
            "draft": bool(i.get("draft")),
            "url": i["html_url"],
        }
        for i in issues
        if "pull_request" in i
    ]


def parent_of(repo: str, issue: dict) -> int | None:
    """The parent's number: the sub-issue parent in this repo, else the one the body names."""
    url = issue.get("parent_issue_url")
    if url:
        m = re.search(rf"/repos/{re.escape(repo)}/issues/(\d+)$", url)
        return int(m[1]) if m else None
    m = BODY_PARENT.search(issue.get("body") or "")
    return int(m[1] or m[2]) if m else None


# The kinds of Work item each skill is meant for; a skill not listed is never flagged.
EXPECTED_KINDS: dict[str, list[Kind]] = {
    "implement": [TICKET],
    "implement-spec": [SPEC],
    "to-tickets": [SPEC],
    "to-spec": [MAP],
    "wayfinder": [MAP],
}


def skill_start(event: dict, repo: str) -> tuple[str, int] | None:
    """The skill an event starts and the Work item its args name: a typed `/skill #N`, or the Skill tool.

    The item is a bare `#N`, or an issue URL in the session's own repo.
    """
    match event.get("hook_event_name"), event.get("tool_name"):
        case "UserPromptExpansion", _:
            skill, args = event.get("command_name"), event.get("command_args")
        case "PreToolUse", "Skill":
            tool_input = event.get("tool_input") or {}
            skill, args = tool_input.get("skill"), tool_input.get("args")
        case _:
            return None
    issue_ref = re.compile(rf"(?:^|\s)#(\d+)\b|github\.com/{re.escape(repo)}/issues/(\d+)\b")
    m = issue_ref.search(args or "")
    if not skill or not m:
        return None
    return skill.rpartition(":")[2], int(m[1] or m[2])  # `mattpocock-skills:implement` → `implement`


def expected_kinds(skill: str, kind: Kind | None) -> list[Kind] | None:
    """The kinds the skill expects, when it started against a Work item of another kind; else None."""
    expected = EXPECTED_KINDS.get(skill)
    return expected if expected and kind and kind not in expected else None
