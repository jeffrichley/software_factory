"""GitHub, read only through `gh api` with the human's existing login. Never written to."""

import json
import subprocess
from typing import Any, Protocol

PAGE = 100


class GitHub(Protocol):
    def api(self, path: str) -> Any: ...


class GhCli:
    def __init__(self, gh: list[str] | None = None) -> None:
        self.gh = gh or ["gh"]

    def api(self, path: str) -> Any:
        # Always an explicit GET: the Factory never writes to GitHub.
        cmd = [*self.gh, "api", "--method", "GET", path]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30).stdout
        return json.loads(out)


def read_issues(github: GitHub, repo: str) -> list[dict]:
    """Every issue and PR in the repo (GitHub lists PRs as issues), open and closed."""
    issues: list[dict] = []
    page = 1
    while True:
        batch = github.api(f"repos/{repo}/issues?state=all&per_page={PAGE}&page={page}")
        issues += batch
        if len(batch) < PAGE:
            return issues
        page += 1
