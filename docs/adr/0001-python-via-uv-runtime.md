# Python via uv is the Factory's only runtime

The hook, the `factory` CLI and the Factory server are all Python ≥3.12 scripts launched only through `uv run --script`, so uv is the one prerequisite on every Machine (WSL, Windows PowerShell, macOS) and no bash or Git Bash is needed anywhere. Scripts may declare third-party deps in PEP 723 frontmatter, each locked with a committed `uv lock --script` lockfile; the hook alone stays stdlib-only, because it runs on every event in every session and must never stall on an install or a slow import.

## Considered Options

- **Node ≥22**: about twice as fast to start (27ms vs 71ms on WSL), but the human prefers Python; ~70ms (WSL) / ~165ms (Windows) per hook event was accepted.
- **Bare `python`**: the command name differs per platform (`python`, `python3`, `py`), Windows ships a Microsoft Store `python3.exe` stub, and system versions are old (3.10 on WSL, 3.9 on macOS); uv removes all of that.
- **Compiled binary (Go/Rust/Bun)**: fastest and no prerequisite, but needs a build and per-platform release binaries, unlike a plain plugin repo built like superpowers.
