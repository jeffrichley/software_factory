"""Seam 2 harness: the hook and `factory` CLI as real `uv run --script` processes,
in temporary git repos, talking to a fake Factory server."""

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "factory-hook"
FACTORY = ROOT / "bin" / "factory"


class FakeServer:
    """Records every POSTed envelope and answers with `reply`."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        self.reply: dict = {"session_id": "7", "job_id": None, "server_version": "0.1.0"}
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers["Content-Length"]))
                server.received.append({"path": self.path, "body": json.loads(body)})
                out = json.dumps(server.reply).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *args) -> None:
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    s = FakeServer()
    yield s
    s.close()


@pytest.fixture
def env(tmp_path) -> dict:
    """A Machine with no Factory setup yet, isolated from the real ~/.claude."""
    claude = tmp_path / "claude"
    (claude / "plugins").mkdir(parents=True)
    (claude / "plugins" / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": {"mattpocock-skills@mattpocock": [{"version": "1.3.1"}]}})
    )
    e = {**os.environ, "CLAUDE_CONFIG_DIR": str(claude)}
    e.pop("CLAUDE_PLUGIN_DATA", None)
    return e


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path) -> Path:
    r = tmp_path / "widgets"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "remote", "add", "origin", "https://github.com/jeff/widgets.git")
    git(r, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init")
    return r


def run_factory(env: dict, cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "--quiet", "--script", str(FACTORY), *args],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=120,
    )


def run_hook(env: dict, event: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "--quiet", "--script", str(HOOK)],
        input=json.dumps(event), cwd=event["cwd"], env=env, capture_output=True, text=True, timeout=60,
    )
