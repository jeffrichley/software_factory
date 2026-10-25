# Multi-session managers and dashboards: survey

Answers issue #4 (child of Map #1). Researched 2026-10-25 against official docs and source repos (shallow clones, read only, never run). Terms follow `GLOSSARY.md`: **Tracked session**, **Job**, **Needs you**, **Done**.

## Question

How do multi-session managers (claude-squad, Conductor, Crystal, vibe-kanban and similar) discover sessions, collect state, detect a session that **Needs you** or is **Done**, isolate work, and present it? Which run on WSL, Windows and macOS?

## Short answer

There are three ways to get state, and the field is moving from the first to the second:

1. **Screen-scraping a PTY/tmux pane** (claude-squad, ccmanager, agent-deck as a fallback). This is fragile: it matches UI strings like `"No, and tell Claude what to do differently"` and breaks when Claude Code changes its TUI.
2. **Claude Code hooks writing to a local sink** (agent-deck, Superset, cmux). Hooks are installed **globally** in `~/.claude/settings.json` and gated on an env var that the manager sets only in its own terminals, so unmanaged sessions are ignored. `Stop` means the turn is over; `PermissionRequest` and `Notification` (matchers `permission_prompt`, `elicitation_dialog`) mean **Needs you**.
3. **Owning the process through headless stream-json or the Agent SDK** (Crystal, vibe-kanban, Conductor, Nimbalyst). The manager runs `claude -p --output-format stream-json` and answers permission and `AskUserQuestion` requests itself, so it always knows the state. The cost is that the session is no longer the normal interactive TUI.

**New since May 2026:** Claude Code ships **Agent View** (`claude agents`), a first-party multi-session dashboard backed by a supervisor daemon. `claude agents --json` reports a `state` and a `waitingFor` field per session. That makes it a supported, non-scraping state source.

Almost every tool puts one git worktree per session under an app-owned directory. Only Agent View, ccmanager, vibe-kanban, Crystal (Windows build) and Nimbalyst run natively on Windows. tmux-based tools need WSL there. Conductor and cmux are macOS only.

## Tool by tool

### claude-squad (smtg-ai/claude-squad, Go TUI, ~8.7k stars, last push 2026-08-20)
- **Discovery:** it only knows the sessions it created, each in its own tmux session. Instances are stored in its config dir (`config/config.go` `GetConfigDir`).
- **State:** every 500 ms (`app/app.go` `tickUpdateMetadataCmd`) it runs tmux `capture-pane` and hashes the result. If the hash changed the session is `Running`, otherwise `Ready` (`session/tmux/tmux.go` `HasUpdated`).
- **Needs you:** it substring-matches the pane for `"No, and tell Claude what to do differently"` (Claude), `"(Y)es/(N)o/(D)on't ask again"` (Aider) or `"Yes, allow once"` (Gemini). In AutoYes mode (`-y`, or the daemon) it presses Enter automatically (`session/instance.go` `TapEnter`, `daemon/daemon.go`).
- **Done:** there is no separate Done state. "Output stopped changing" (`Ready`) covers both finished and waiting.
- **Isolation:** `git worktree add` under `~/.claude-squad/worktrees/<branch>` (`session/git/worktree.go`).
- **UI:** a Bubble Tea TUI with a list, preview and diff tab. There is a Next.js `web/` folder, but it is a landing page.
- **Platforms:** macOS and Linux via brew or install.sh, and it requires tmux. A `tmux_windows.go` build exists, but tmux does not run natively on Windows, so in practice Windows means WSL.

### ccmanager (kbwo/ccmanager, TS/Bun TUI, ~1.3k stars, active 2026-10)
- **Discovery:** it lists the repo's git worktrees and the sessions it spawned. Sessions are persisted in `~/.config/ccmanager/sessions.json` (`%APPDATA%\ccmanager\sessions.json` on Windows) (README).
- **State:** it runs each agent in its own PTY and renders the output in `@xterm/headless`. A detector for each agent reads the last 30 lines (`src/services/stateDetector/claude.ts`). The states are `idle | busy | waiting_input | pending_auto_approval` (`src/types/index.ts`).
- **Needs you:** a regex for `do you want|would you like` followed by an option list, `esc to cancel`, or `N. Deny (esc)`.
- **Busy:** `esc to interrupt`, a spinner line matching `…ing…`, or a token-stats line.
- **Done:** it reports `idle` once the screen has been unchanged for 1.5 s (`IDLE_DEBOUNCE_MS`), as a workaround for false idles. It also counts background tasks and team members from the footer.
- **Hooks out:** "status hooks" run a user command on each state change, with `CCMANAGER_OLD_STATE`, `CCMANAGER_NEW_STATE`, `CCMANAGER_WORKTREE_PATH`, `CCMANAGER_SESSION_ID` and others (`src/components/ConfigureStatusHooks.tsx`).
- **Platforms:** macOS, Linux and native Windows.

### agent-deck (asheshgoplani/agent-deck, Go TUI + web, ~1.2k stars, active 2026-10)
- **Discovery:** sessions it launched in tmux. It injects `AGENTDECK_INSTANCE_ID` into each session's environment.
- **State, primarily from hooks:** it writes hook entries into Claude's `settings.json` (`internal/session/claude_hooks.go`) for `SessionStart`, `UserPromptSubmit` (sync), `PreToolUse`, `Stop` (sync), `PermissionRequest` (sync), `Notification` with matcher `permission_prompt|elicitation_dialog`, and `SessionEnd`. The handler `agent-deck hook-handler` exits silently when `AGENTDECK_INSTANCE_ID` is unset, which makes it an opt-in gate. It maps events to statuses: `UserPromptSubmit`/`PreToolUse` → running, `Stop` → waiting, `PermissionRequest` → waiting, `SessionEnd` → dead (`cmd/agent-deck/hook_handler.go` `mapEventToStatus`). It writes `~/.agent-deck/hooks/<id>.json` plus an `.events.jsonl` log, and the TUI watches them with fsnotify (`internal/session/hook_watcher.go`).
- **Fallback:** it polls the tmux pane.
- **Needs you vs Done:** a session is `Waiting` (yellow, "needs your input") until the human looks at it. After that "acknowledged" flag is set it becomes `Idle` (grey). New activity resets the acknowledgement (`internal/session/instance.go`). This attention model is close to what the Factory wants.
- **Presentation:** a TUI, a tmux status-bar list of waiting sessions, `agent-deck web` on `127.0.0.1:8420` (README notes Tailscale Serve), and desktop notifications through cmux, `notify-send` or `osascript` (`internal/desknotify`).
- **Isolation:** `--worktree`, with a configurable location (sibling, `.worktrees/` subdirectory, or a custom path), `.worktreeinclude`, and setup and destroy scripts.
- **Platforms:** macOS, Linux and WSL. There is no native Windows build.

### Crystal (stravu/crystal, Electron) is deprecated; its successor is Nimbalyst
- Crystal was **deprecated in February 2026** in favour of Nimbalyst (README). It is still informative as a design:
  - It runs `claude --verbose --output-format stream-json` headless for each turn (`main/src/services/panels/claude/claudeCodeManager.ts`).
  - Its approve mode uses `--permission-prompt-tool mcp__crystal-permissions__approve_permission`, an MCP bridge that turns permission prompts into UI dialogs.
  - It sets `waiting` on a stream-json `prompt` message (`main/src/events.ts`).
  - On process exit with code 0 it sets `completed_unviewed` ("Done, not yet seen"), which clears once the user views the session. Otherwise the status is `stopped`.
  - Builds existed for macOS, Linux and Windows (`package.json`).
- **Nimbalyst** (nimbalyst/nimbalyst, MIT, ~2k stars, active 2026-10) is a desktop app for macOS, Windows and Linux with an iOS companion. It isolates each session in a worktree and is built on `@anthropic-ai/claude-agent-sdk` (`packages/runtime/package.json`).

### vibe-kanban (BloopAI/vibe-kanban, Rust + React web UI, ~28k stars) is sunsetting
- **Status:** the shutdown was announced 2026-04-10. The hosted service ended and the project continues as a local, community-maintained open-source edition (vibekanban.com/blog/shutdown). The last push was 2026-09-19.
- **How it runs Claude:** `claude -p --output-format=stream-json --input-format=stream-json --include-partial-messages --replay-user-messages`, plus `--permission-prompt-tool=stdio` when approvals or plan mode are on (`crates/executors/src/executors/claude.rs`). It answers `can_use_tool` control requests over stdio (`claude/client.rs`) and registers `PreToolUse` hook callbacks for `AskUserQuestion` and `ExitPlanMode`. So **Needs you** is a pending approval or question in its own approvals service.
- **Done:** it tracks the execution process's lifecycle (`Running` → `Completed`/`Failed`/`Killed`, in `crates/db/src/models/execution_process.rs`). The task then moves to `InReview` on the board.
- **Isolation:** `git worktree add` under the app temp dir `…/worktrees` or `<custom>/.vibe-kanban-workspaces` (`crates/worktree-manager`).
- **Notifications** (`crates/services/src/services/notification.rs`) are a useful cross-platform reference:
  - macOS: `afplay` and `osascript`.
  - Linux: `notify-rust`.
  - **Windows and WSL2:** `powershell.exe` toast and sound. On WSL2 it detects the environment and converts paths with `wslpath`.
- **Platforms:** `npx vibe-kanban` on macOS, Linux, Windows and WSL.

### Conductor (conductor.build, closed source, Mac app)
- Runs Claude Code, Codex, Cursor and OpenCode in parallel. Each workspace is an isolated git worktree with its own branch, plus a `.context` folder and setup scripts (docs/concepts/workspaces-and-branches).
- It bundles its own copies of Claude Code and Codex (FAQ). Files live in `~/Library/Application Support/com.conductor.app` and `~/conductor` (FAQ).
- **"Conductor is available for macOS. Conductor is not available for Windows or Linux yet."** (docs/installation)
- The public docs do not describe how it detects waiting or done, and the source is closed, so this survey cannot say.

### cmux (manaflow-ai/cmux, Swift/Ghostty terminal, ~28k stars, active 2026-10)
- It is a terminal rather than an orchestrator. It picks up OSC 9/99/777 notification escape sequences and offers a `cmux notify` CLI that agent hooks can call. `cmux hooks setup` installs hooks for Claude Code, Codex and others.
- A waiting pane gets a blue ring, and a sidebar shows each workspace's branch, PR, ports and latest notification (README).
- It is **macOS only**.

### Superset (superset-sh/superset, Electron, ~15.5k stars, active 2026-10)
- It runs agent CLIs in its own terminals, one worktree per workspace.
- It writes hooks into global agent configs such as `~/.claude/settings.json`. The hook script exits unless `SUPERSET_TERMINAL_ID` or `SUPERSET_TAB_ID` is set, and otherwise `curl`s a POST to a localhost host service (`packages/agent-setup/templates/notify-hook.template.sh`).
- It maps events to states: `UserPromptSubmit`/`PostToolUse` → Start, `PermissionRequest`/`Notification`/`PreToolUse` → PermissionRequest (Needs you), `Stop` → Stop (`apps/desktop/src/main/lib/notifications/map-event-type.ts`).
- **Platforms:** macOS, with an experimental Linux build. **No Windows.**

### Claude Code Agent View (first party, research preview since 2026-05, v2.1.139+)
- `claude agents` opens a TUI listing **background** sessions across projects. Interactive sessions in other terminals appear only after `/bg` (code.claude.com/docs/en/agent-view).
- A supervisor daemon (`claude daemon status|logs|stop`) runs the sessions, which survive closing the terminal. State is kept in `~/.claude/daemon/roster.json` and `~/.claude/jobs/<id>/state.json`. The docs say to read it through the CLI rather than parse those files.
- **`claude agents --json`** returns, for each session:
  - `cwd`, `kind` (`interactive`|`background`) and `startedAt`.
  - `state`: `working | blocked | done | failed | stopped`.
  - `status`: `busy | waiting | idle`.
  - `waitingFor`: `permission prompt | input needed | sandbox request | worker request | dialog open`.
  - `sessionId` and `name`.
- **Needs input** is defined as "waiting on something only you can provide: an answer to a question, a permission decision…". The view groups `Ready for review` sessions (open PR needing review or with failing checks), `Needs input`, and `Completed`.
- **Isolation:** before its first edit, a background session moves into its own worktree under `.claude/worktrees/`. This is configurable with `worktree.bgIsolation`.
- **Notifications:** while agent view is open, it fires the `Notification` hook with `agent_needs_input` or `agent_completed`.
- **Platforms:** it ships inside Claude Code. The docs mention Windows behaviour, but this survey found no explicit support matrix.

## Relevant Claude Code hook facts (code.claude.com/docs/en/hooks)
- **Notification matchers:** `permission_prompt`, `idle_prompt`, `elicitation_dialog`, `elicitation_url_dialog`, `agent_needs_input`, `agent_completed`, and others.
- **Other relevant events:** `Stop`, `StopFailure`, `PermissionRequest`, `SessionStart`, `SessionEnd`, `SubagentStart`/`SubagentStop`, and `WorktreeCreate`/`WorktreeRemove`.
- **Common input fields:** `session_id`, `transcript_path`, `cwd` and `permission_mode`.
- **HTTP hooks** exist: the payload is POSTed directly, with no shell involved.
- **On Windows,** command hooks run in Git Bash by default and fall back to PowerShell. This can be set with `"shell"`.

## Platform matrix

| Tool | State source | macOS | Linux/WSL | Windows native |
|---|---|---|---|---|
| Agent View (`claude agents`) | first-party daemon + `--json` | yes | yes | yes (Windows behaviour documented) |
| claude-squad | tmux pane scrape | yes | yes | no (tmux) |
| ccmanager | PTY + xterm-headless scrape | yes | yes | yes |
| agent-deck | hooks → files, tmux fallback | yes | yes | no (WSL) |
| Crystal → Nimbalyst | stream-json / Agent SDK | yes | yes | yes |
| vibe-kanban | stream-json + stdio permission tool | yes | yes (WSL-aware) | yes |
| Conductor | closed source | yes | no | no |
| cmux | OSC sequences + hooks | yes | no | no |
| Superset | hooks → localhost POST | yes | experimental | no |

## Implications for the Factory
- **Hooks are the right primary signal** because the skills must run unmodified in a normal interactive session. Map them as follows:
  - **Needs you:** `PermissionRequest`, plus `Notification` with `permission_prompt`, `elicitation_dialog` or `idle_prompt`. These cover a question, a permission prompt and an escalation; a HITL ticket would still need a Factory-specific signal.
  - **Done:** `Stop` or `SessionEnd` with nothing pending.
  - **Not done:** `UserPromptSubmit` or `PreToolUse` mean running again.
- **Proven opt-in pattern** (agent-deck, Superset): install hooks globally, or per Tracked repo through the install command, and have the hook exit unless a Factory env var or opt-in marker is present. That matches "sessions opt in with a slash command".
- **Transport:** an HTTP hook POSTing to the dashboard (Superset) needs no shell, which suits Windows. Files plus a watcher (agent-deck) survive the dashboard being down. Either works on WSL, PowerShell and macOS.
- **Acknowledge model:** agent-deck's waiting→idle-on-view and Crystal's `completed_unviewed` show how to keep **Done** visible until the human has seen it.
- **Agent View** is a possible extra source for background sessions (`claude agents --json`). It is a research preview, and it does not cover foreground sessions unless they are backgrounded.
- **Notifications:** vibe-kanban's code is a working example for macOS, Linux, Windows and WSL (PowerShell toast from inside WSL).
- **Avoid screen-scraping.** Its maintainers document the false idles and the dependence on UI strings.
