"""Work items: a Tracked repo's issues that have a kind, taken from GitHub structure alone (never from the skill)."""

import re
from typing import Literal

from .jobs import closed_by
from .wayfinder import map_of, type_of

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


def work_items(repo: str, issues: list[dict], blocked_by: dict[int, list[int]] | None = None) -> list[dict]:
    """The repo's Work items: its issues (PRs left out) that are a Map, Decision ticket, Spec or Ticket, each with
    its parent's number and the issues that block it (`blocked_by`, read separately)."""
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
        if parent_kind in (SPEC, TICKET):
            return TICKET  # a Ticket split again (an Epic) has Tickets of its own, at any depth
        if parent_kind == MAP:
            return DECISION_TICKET
        body = issue.get("body") or ""
        if all(section in body for section in SPEC_SECTIONS):
            return SPEC
        if parent is None and (issue.get("sub_issues_summary") or {}).get("total"):
            return SPEC  # to-tickets split it into Tickets
        return None

    rows = [
        {"number": n, "title": i["title"], "state": i["state"], "url": i["html_url"], "kind": kind(n),
         "parent": parent_of(repo, i), "blocked_by": (blocked_by or {}).get(n, []),
         # A Decision ticket's type and claim; a Map's Destination, fog, gists and what is out of scope.
         "type": type_of([label["name"] for label in i.get("labels", [])]),
         "assignees": [a["login"] for a in i.get("assignees") or [] if isinstance(a, dict) and a.get("login")],
         "map": map_of(i.get("body"), repo) if kind(n) == MAP else None}
        for n, i in by_number.items()
    ]
    return [row for row in rows if row["kind"]]


def pull_requests(issues: list[dict]) -> list[dict]:
    """The repo's PRs, each open, closed or merged, whether it is a draft, and the issues its body closes."""
    return [
        {
            "number": i["number"],
            "title": i["title"],
            "state": "merged" if i["pull_request"].get("merged_at") else i["state"],
            "draft": bool(i.get("draft")),
            "url": i["html_url"],
            "closes": closed_by(i.get("body")),
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
