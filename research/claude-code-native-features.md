# Claude Code's native observation and orchestration features

Research for #5 (child of map #1). Question: what does Claude Code natively offer for observing and orchestrating sessions, and can a plugin observe or wrap a skill run without modifying the skill? Per-platform behaviour for WSL, Windows PowerShell and macOS.

Sources: official docs at `code.claude.com/docs/en/*.md`, fetched 2026-10-25, and the local install (Claude Code **v2.1.310** on WSL2). Each claim cites a doc page (`hooks` = `code.claude.com/docs/en/hooks`, and so on) or "local".

## Answer in brief

- **Yes, the Factory can observe skills without modifying them.** A plugin's `hooks/hooks.json` is active for the whole session as soon as the plugin loads (plugins/components). Two hooks between them cover both ways a skill starts:
  - **Claude calls the skill:** `PreToolUse`/`PostToolUse` with matcher `Skill`.
  - **The human types `/skill`:** `UserPromptExpansion`, matched on `command_name`. The hooks docs say plainly that typing `/skillname` skips `PreToolUse` and that `UserPromptExpansion` covers that path (hooks#userpromptexpansion).
  - **Wrapping, not just watching:** both hooks can add `additionalContext` or block. A **mod** (a JS hooks module inside a plugin) can also rewrite a skill's text before Claude reads it, through `skill.prompt` (plugins/mods/reference).
- **No native "skill finished" event exists.** The `Skill` tool returns as soon as the skill text loads: its result is `Launching skill: <name>`, and the skill body then arrives as the next user message (local transcript). So `PostToolUse(Skill)` means "skill loaded", not "skill done". A skill's work ends with the turn, at the next `Stop`. A Job therefore has to be bounded by `Stop`, plus `SubagentStart`/`SubagentStop` for the subagents a skill spawns.
- **Hooks that signal each Needs you / Done case:**

| Signal | Event (immediate) | Event (delayed / fallback) |
| :- | :- | :- |
| Permission prompt | `PermissionRequest` (fires the moment the dialog would show) | `Notification` `permission_prompt` (only after about 6 s of no typing) |
| Question to the user | `PreToolUse` matcher `AskUserQuestion` (and `ExitPlanMode` for plan approval) | `Notification` `elicitation_dialog` / `elicitation_url_dialog` for MCP elicitations; `Elicitation` hook |
| Subagent start / stop | `SubagentStart` / `SubagentStop` (matcher = agent type); `PostToolUse` on `Agent` carries result and telemetry | |
| Finished turn | `Stop` (not on user interrupt); `StopFailure` on API error | `Notification` `idle_prompt` (about 60 s later, only if idle) |
| Session ends | `SessionEnd` | |
| Agent-team teammate idle | `TeammateIdle` | |

- **Claude Code now has its own Needs you / Done model:** agent view (`claude agents`, research preview). `claude agents --json --all` reports each session's `state` (`working`, `blocked`, `done`, `failed`, `stopped`) and a `waitingFor` field (`permission prompt`, `input needed`, …). It only covers *background* sessions (agent-view).

## 1. Hook events (full list)

Source: hooks#hook-lifecycle. Hook types: `command`, `http` (POSTs the JSON input to a URL), `mcp_tool`, `prompt`, `agent` (hooks#hook-handler-fields). The `http` type lets the Factory's dashboard receive events directly, with no script per platform.

| Event | Fires | Matcher on | Can block? |
| :- | :- | :- | :- |
| `SessionStart` | session begins/resumes | `startup`/`resume`/`clear`/`compact`/`fork` | no (context, `sessionTitle`, `initialUserMessage`) |
| `Setup` | `--init-only`, `--init`/`--maintenance` in `-p` | `init`/`maintenance` | |
| `InstructionsLoaded` | CLAUDE.md / rules loaded | load reason | |
| `UserPromptSubmit` | prompt submitted (also `/loop` ticks, background subagent reports, cross-session messages) | none | yes |
| `UserPromptExpansion` | user-typed `/command` expands | `command_name` | yes |
| `MessageDisplay` | assistant text streams | none | display only |
| `PreToolUse` | before every tool call | tool name | yes (allow/deny/ask/defer, `updatedInput`) |
| `PermissionRequest` | a tool call needs a permission decision | tool name | yes (allow/deny on user's behalf) |
| `PermissionDenied` | auto mode denies a call | tool name | `retry` |
| `PostToolUse` / `PostToolUseFailure` | after a tool succeeds/fails | tool name | feedback |
| `PostToolBatch` | after a batch of parallel tool calls | none | |
| `Notification` | Claude Code sends a notification | notification type | no |
| `SubagentStart` / `SubagentStop` | subagent spawned/resumed / finished | agent type | Stop: yes (keeps subagent running) |
| `TaskCreated` / `TaskCompleted` | `TaskCreate` / task marked done | none | yes |
| `Stop` / `StopFailure` | turn finished / ended on API error | none / error type | Stop: yes (continue turn) |
| `TeammateIdle` | agent-team teammate about to idle | none | yes |
| `ConfigChange`, `CwdChanged`, `DirectoryAdded`, `FileChanged` | config/cwd/dir/watched-file changes | varies | |
| `WorktreeCreate` / `WorktreeRemove` | `--worktree`, `isolation: "worktree"`, background session | none | replaces git behaviour |
| `PreCompact` / `PostCompact` | compaction | `manual`/`auto` | |
| `PreModelSwitch` / `PostModelSwitch` | model switch | model name | Pre: yes |
| `Elicitation` / `ElicitationResult` | MCP server asks user for input | server name | yes |
| `SessionEnd` | session terminates | reason | no |

Key payload facts (hooks#common-input-fields):
- **Every event carries** `session_id`, `prompt_id`, `transcript_path`, `cwd`, `hook_event_name`, and usually `permission_mode`. Events inside a subagent also carry `agent_id` and `agent_type`, so tool calls can be attributed to a subagent, and so to a Step.
- **The transcript can lag.** It is written asynchronously, so use `last_assistant_message` on `Stop`/`SubagentStop` rather than reading the file (hooks#stop-input).
- **`Stop` can tell "done" from "paused".** It includes `background_tasks` and `session_crons`, which separate "session is done" from "session is paused waiting on background work" (hooks#stop-input). This matters for a Done signal.
- **`SubagentStop` carries more.** It includes `agent_transcript_path` (`<session>/subagents/agent-<id>.jsonl`) and `last_assistant_message`. It also fires for internal agents (prompt suggestions, `/btw`), which have an empty `agent_type`, so a match-all matcher must filter these out (hooks#subagentstop).
- **`PostToolUse` on `Agent` carries telemetry.** It returns `status` (`completed` or `async_launched`), `agentId`, `totalDurationMs`, `totalToolUseCount`, and `usage` (hooks#agent).
- **The `PermissionRequest` docs name the delay:** "Claude Code runs a Notification hook with the `permission_prompt` type only after the prompt has waited about six seconds" (hooks#permissionrequest). Background or `-p` sessions with no prompt still run `PermissionRequest`, then auto-deny.
- **The timings of `Notification` types** (hooks#notification):
  - `permission_prompt`: about 6 s, deferred by each keystroke.
  - `idle_prompt`: about 60 s after Stop, only if no typing and no background agent.
  - `agent_needs_input` / `agent_completed`: only while agent view is open.
  - These fire even when desktop notifications are off.
- **`async: true`** runs a command hook without blocking. That is right for pure telemetry to a dashboard (hooks#run-hooks-in-the-background).
- **`terminalSequence`** output lets any hook raise an OSC 9/99/777 desktop notification or a BEL through Claude Code's own terminal write. It works in Windows Terminal, iTerm2, Ghostty, Kitty, WezTerm and tmux, but only in interactive sessions (hooks#emit-terminal-notifications).

## 2. Observing and wrapping a skill run

| Path | What fires | What the hook sees | Can it wrap? |
| :- | :- | :- | :- |
| Claude calls the `Skill` tool | `PreToolUse` / `PostToolUse` matcher `Skill` | `tool_input.skill` (e.g. `mattpocock-skills:research`), `agent_id` if inside a subagent | `additionalContext`, deny, `updatedInput` |
| Human types `/skill args` | `UserPromptSubmit` (raw line as typed, not expanded) **and** `UserPromptExpansion` | `command_name`, `command_args`, `command_source` (`plugin`, …), `expansion_type: slash_command` | block or `additionalContext` |
| Mod (JS hooks module in a plugin) | `skill.prompt` | `e.skill`, `e.text`, `e.source`, `e.pluginName`, `e.path`, `e.frontmatter` | rewrite `text` before Claude reads it |

Sources: hooks#userpromptexpansion, hooks#userpromptsubmit-input, plugins/mods/reference#prompts-and-what-claude-reads.

Local evidence (transcript under `~/.claude/projects/-mnt-e-workspaces-ai-tools/<session>/subagents/agent-*.jsonl`):
- A `tool_use` with `name: "Skill"` and `input: {"skill": "mattpocock-skills:research"}`.
- The `tool_result` comes back about 9 s later with the text `Launching skill: mattpocock-skills:research` and `toolUseResult.commandName`.
- Then comes a `user` message holding `Base directory for this skill: …` plus the SKILL.md body.
- So the skill "run" is everything until the turn's `Stop`, and no event marks the end of the skill as such.
- A typed slash command shows up in the transcript as `<command-name>/name</command-name><command-args>…`.

Other points:
- **Plugin hooks are not tied to the plugin's own skills.** They "register when a session loads the plugin, and they fire on their events from then on" (plugins/components#when-plugin-hooks-fire). One Factory plugin can therefore observe Matt Pocock's plugin's skills.
- **Skill frontmatter `hooks:` are not usable here.** They live in the skill file, and the skills must stay unmodified (hooks#hooks-in-skills-and-agents).
- **What this means for Jobs:** to attribute work to a Job, key on `session_id`, and on `agent_id` for subagents. Mark the skill start from `UserPromptExpansion` or `PreToolUse(Skill)`, and the end from `Stop`. `implement-spec`'s per-Ticket subagents show up as `SubagentStart`/`SubagentStop`, which can serve as candidate Steps.

## 3. Session transcripts on disk

- **Location:** `~/.claude/projects/<project>/<session-id>.jsonl`. `<project>` is the launch cwd with non-alphanumerics turned into `-`, truncated to 200 characters plus a hash (sessions#where-transcripts-are-stored).
  - Local: the directory follows the session's **launch** cwd. A subagent working in a worktree still writes under the parent's project directory.
- **Subagents:** `<session>/subagents/agent-<id>.jsonl`, plus a `agent-<id>.meta.json`. The meta file holds `agentType`, `worktreePath`, `worktreeBranch`, `description`, `toolUseId` and `requestShape` (local; claude-directory#application-data).
- **Other per-session files:** large outputs go in `<session>/tool-results/`. `custom-title.json` was seen locally.
- **A supported interface?** The docs call transcripts plaintext but do not define the JSONL as a stable API. The supported routes are the `transcript_path` passed to hooks and status lines, `--output-format json/stream-json`, and the Agent SDK (sessions#export-and-locate-session-data).
- **Retention:** `cleanupPeriodDays`. `CLAUDE_CONFIG_DIR` relocates everything.

## 4. Subagents, agent teams, agent view, cross-session messaging

- **Subagents:** they run inside one session, can run in the foreground or background, and can use `isolation: "worktree"`. `SubagentStart`/`SubagentStop` fire for them. Agent view does not list them as rows (agent-view, sub-agents).
- **Agent teams:** *experimental*, off by default, enabled with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.
  - A lead plus teammates with a shared task list and direct messages.
  - Hooks: `TeammateIdle`, `TaskCreated`, `TaskCompleted`. `SubagentStart` fires each time an in-process teammate handles a message.
  - Split panes need tmux or iTerm2. The default display mode is in-process (agent-teams).
- **Agent view and background sessions** (research preview), from the agent-view page:
  - **Launch:** `claude --bg "prompt"` (with `--name`, `--agent`, `--resume`), or `/bg` or `←` from a running session.
  - **Hosting:** a supervisor daemon hosts each session as its own process, which survives closing the terminal.
  - **States:** Working, Needs input, Idle, Completed, Failed, Stopped.
  - **Scripting:** `claude agents --json [--all] [--cwd]` returns `state`, `status` (`busy`/`waiting`/`idle`), `waitingFor` and `sessionId`. The docs call it "the supported way to read session state from outside Claude Code". Files under `~/.claude/jobs/<id>/` are explicitly *not* stable.
  - **Control:** `claude attach|logs|stop|respawn|rm <id>`.
  - **Notifications:** while agent view is open, it notifies through `preferredNotifChannel` and fires `Notification` `agent_needs_input` / `agent_completed`.
  - **Coverage gap:** interactive sessions in other terminals do not appear until backgrounded, and `--json` lists them only with limited fields.
  - **Worktrees:** a background session with worktree isolation commits, pushes its own branch and opens a draft PR when it finishes (agent-view changelog, v2.1.198).
- **Cross-session messaging:** sessions on one machine can `ListAgents`/`SendMessage` over Unix sockets (macOS, Linux, WSL2) or named pipes (native Windows). **A WSL2 session and a native Windows session on the same PC cannot reach each other** (cross-session-messaging#availability).

## 5. Slash commands, mods, monitors, channels, status line

- **Slash commands and skills:** commands are now skills (the `slash-commands` page serves the skills doc). A plugin ships them under `skills/` or `commands/`. A plugin command can launch a Job (plugins/components).
- **Mods (plugin JS hooks module):**
  - **Where:** a mod is declared under `modules` in `hooks/hooks.json` and runs **inside** Claude Code (plugins/mods/overview, reference).
  - **Interface:** it can draw panes or a band.
  - **Events it handles:** `tool.call`, `tool.check`, `skill.prompt`, `prompt.submit`, `turn.start`, `turn.complete`, `agent.spawn`, `session.start`, `session.end`, `session.append` (every stored transcript row), and `classic.<HookEvent>`.
  - **What it can call:** `$.http.fetch`, `$.ui.notify`, and messaging between sessions.
  - **Where it runs:** CLI, Desktop and VS Code. In `-p`/SDK its hooks run but nothing draws. It does **not** run in Desktop-app WSL sessions (plugins aren't available there).
  - **Fit:** a plausible in-session complement to a web dashboard.
- **Monitors:** in `monitors/monitors.json`, a background shell command whose output reaches Claude as notifications. They run in interactive sessions only (plugins/components#monitors).
- **Channels:** an MCP server that pushes messages into a session. With the *permission relay* capability it can forward permission prompts for remote approval (channels, channels-reference).
- **Status line:** a script that receives session JSON (including `transcript_path`), debounced at 300 ms, with an optional `refreshInterval` (statusline). It is a weak observation channel, so hooks are better.

## 6. Remote Control and push notifications

- **What it is:** `claude remote-control` (server mode, up to 32 concurrent sessions, `--spawn worktree`), or `claude --remote-control` / `/remote-control` for one session. The local session becomes reachable from claude.ai/code and the Claude mobile app, while execution stays local (remote-control).
- **Requirements:** a Pro/Max/Team/Enterprise claude.ai login. It does not work with API keys, Bedrock/Vertex/Foundry, or a custom `ANTHROPIC_BASE_URL`.
- **Prompts stay open:** permission prompts and `AskUserQuestion` are forwarded and stay open until answered.
- **Mobile push:** while Remote Control is active, `/config` offers **Push when actions required** (permission prompts and questions) and **Push when Claude decides**. Pushes are skipped while you're focused on the terminal. `CLAUDE_CLIENT_PRESENCE_FILE` extends that to "at the machine" (remote-control#mobile-push-notifications).
- **What this means for the Factory:** this is the native path for the deferred "Phone push for Needs you" item, at no build cost. It is per session and goes through Anthropic's servers, not Tailscale.

## 7. Agent SDK and headless

- **Agent SDK (Python/TS):** runs the Claude Code binary as a library. It supports the same hooks as in-process callbacks, `canUseTool` for permission and question prompts, and sessions (agent-sdk/overview, agent-sdk/hooks).
- **Other languages:** use `claude -p --output-format stream-json` (headless).
- **`PreToolUse` `"defer"`** pauses at a tool call so the host can collect input and resume. It works only with `-p` (hooks#defer-a-tool-call-for-later).
- **Relevance:** the SDK is relevant only if the Factory ever *hosts* sessions itself. The map's constraint is that Jobs launch via slash commands in normal sessions, which points to hooks rather than the SDK.

## 8. Per-platform behaviour

| Topic | macOS | WSL2 | Windows PowerShell (native) |
| :- | :- | :- | :- |
| Hook shell (shell form) | `sh -c` | `sh -c` | Git Bash if installed, else PowerShell; `"shell": "powershell"` forces PowerShell (hooks#exec-form-and-shell-form, #windows-powershell-tool) |
| Portable hook command | `node` + script via exec form (`command` + `args`) works everywhere; `.cmd` shims need shell form on Windows | same | same |
| Config dir / transcripts | `~/.claude` | Linux `~/.claude` inside the distro (separate from Windows) | `%USERPROFILE%\.claude` |
| Desktop notification | `osascript` (needs Script Editor permission) or OSC via `terminalSequence`; native in iTerm2/Ghostty/Kitty | `notify-send` needs a daemon; docs suggest `powershell.exe` via interop; `terminalSequence` OSC 9 works in Windows Terminal | `powershell.exe` (docs example is a MessageBox); OSC 9 in Windows Terminal |
| Hook failures | | | Without Git Bash, `PreToolUse`/`PermissionRequest` hooks count only exit codes 0/2 as a verdict; use `onFailure` (hooks#failed-hooks-on-windows-without-git-bash) |
| Cross-session messaging | Unix socket | Unix socket | named pipe + auth line; cannot talk to WSL sessions |
| Agent view supervisor | sessions stop about 1 min after the supervisor dies unless restarted; Local Network / protected-folder permission prompts | as Linux | supported; `taskkill` for a stuck supervisor |
| Desktop app | full | **plugins (so hooks and mods) not available in Desktop WSL sessions** (desktop-wsl) | full |
| Sandboxing | yes | yes (WSL2) | no |

What this means for the Factory:
- **WSL and native Windows are two separate installs on one machine,** each with its own `~/.claude`. The Factory install has to put hooks in both, and they should report to the one dashboard, ideally through `http` hooks to a localhost port.
- **Unverified (not in the Claude Code docs):** whether a WSL2 → Windows-host `localhost` call works depends on WSL networking mode (NAT vs mirrored). Needs a prototype.

## Open questions for later tickets

- Do we rely on `claude agents --json` for Needs you / Done, which is native but covers only background sessions and is a research preview, or on our own hooks, which cover every session? A hybrid is possible.
- Defining a Job's end: `Stop` with empty `background_tasks` is the best Done signal available. A skill that ends its turn by asking a question must be treated as Needs you, not Done. Agent view treats a question-ending turn as "waiting for your next message", and its `blocked` state covers it.
