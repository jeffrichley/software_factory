"""GitHub, read only through `gh api` with the human's existing login. Never written to."""

import json
import subprocess
from typing import Any, Protocol


class GitHub(Protocol):
    def api(self, path: str) -> Any: ...


class GhCli:
    def api(self, path: str) -> Any:
        out = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True).stdout
        return json.loads(out)
