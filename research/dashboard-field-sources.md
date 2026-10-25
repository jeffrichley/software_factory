# Sourcing the dashboard's shaky fields

Research for **Prove the dashboard's shaky fields can be sourced** (#17, child of map #1). Question: for each dashboard field with no known event yet, which source supplies it (Claude Code hooks, a Factory CLI self-report the agent is told to run, GitHub polling, or a transcript peek), and what is the fallback?

Builds on [claude-code-native-features.md](https://github.com/jeffrichley/software_factory/blob/research/claude-code-native-features/research/claude-code-native-features.md) (#5) and the resolutions of #7 (hooks-first, CLI report where hooks can't see) and #16 (the dashboard inventory). Not repeated here.

## Sources and confidence labels

- **docs**: `code.claude.com/docs/en/hooks.md`, `tools-reference.md`, `sub-agents.md`, `plugins-reference.md`, fetched 2026-10-25.
- **skills**: Matt Pocock's skills plugin v1.3.1 at `~/.claude/plugins/cache/mattpocock/mattpocock-skills/1.3.1/skills/` (`engineering/implement`, `implement-spec`, `tdd`, `code-review`, `wayfinder`, `to-tickets`; `productivity/grilling`).
- **experiment**: three `claude -p --model haiku` runs (Claude Code **v2.1.310**, WSL2, model resolved to `claude-haiku-5-5`) with a settings file logging every hook payload for `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `Stop`, `MessageDisplay`. Payloads quoted below are from those logs.

Confidence: **verified** = seen in the experiment; **documented** = stated in the docs, not exercised; **inferred** = reasoned from the above.

## Answer in brief

| # | Field | Best source | Confidence | Fallback |
| :- | :- | :- | :- | :- |
| 1 | Phase | Inferred server-side from hook signals: file edits (test vs source path), test-run pass/fail, `Skill(code-review)`, `git commit`, merge / GitHub PR merged | signals **verified**; the Phase rule is **inferred** | Self-report `factory phase <name>`; else unknown |
| 2 | Spec Job Steps → Ticket | `PostToolUse(Agent)` in the main session: `tool_response.agentId` + `tool_input.prompt`/`description` (parse the Ticket ref); worktree = subagent events' `cwd` | **verified** (join and cwd); the Ticket ref in the prompt is **inferred** (implement-spec only says "context pointers") | `SubagentStart` `additionalContext` tells the subagent to run `factory step --ticket <n>`; else Step shows Ticket unknown |
| 3 | Test pass/fail pulse | `PreToolUse(Bash)` command matched against the Tracked repo's test command; outcome from `PostToolUse` (exit 0) vs `PostToolUseFailure` (`error` starts `Exit code N`) | exit signal **verified**; recognising "the test command" is **inferred** | Per-repo test-command patterns in `.factory/`; self-report `factory test pass|fail`; else no pulse |
| 4 | Agent's live checklist | `PostToolUse(TodoWrite)` `tool_response.newTodos` (full list each call), or `TaskCreated` / `PostToolUse(TaskUpdate)` | **verified**, incl. inside a background subagent with `agent_id`, **but only when the tools are switched on** (off by default on current models) | Factory install sets `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` + `CLAUDE_CODE_ENABLE_TASKS=0`; else checklist unknown |
| 5 | Review findings count | Self-report: `PostToolUse(Skill code-review)` injects context telling the agent to run `factory review --standards N --spec M` after aggregating | **inferred** (mechanism documented, count is model-written) | Parse the code-review summary line from `MessageDisplay`/`Stop` text or the two axis subagents' `PostToolUse(Agent).tool_response.content`; else unknown |
| 6 | Grilling round question titles | `Stop.last_assistant_message` (a round ends the turn) and `MessageDisplay.delta`, regex on grilling's fixed format `❓ **Q<n>** - **<title>**:` | **verified** (text arrives in both payloads) | Self-report `factory round --q "<title>" …`; else unknown |

Transcripts are not needed for any field. Where a peek would help, the hook payload already carries the same data (cost table at the end).

## What the skills actually do (tool calls that matter)

- **implement**: main session. Calls `Skill(tdd)` "at pre-agreed seams", runs typecheck, single test files and the full suite, then `Skill(code-review)`, then commits to the current branch. No subagents of its own except code-review's two.
- **implement-spec**: main session is the orchestrator. Optional exploration subagent; creates the integration branch; **implementer subagents** "each in its own worktree on its own branch", "run in the background where possible"; each implementer calls `Skill(tdd)` and merges the integration tip into its branch; a **merger subagent** merges each into the integration branch; final `Skill(code-review)` on the integration branch, then one fix-up implementer; draft PR → ready. Subagent communication is "primarily through context pointers: to the spec, tickets…", so a Ticket ref in the prompt is likely but not promised.
- **tdd**: red → green, "one seam, one test, one minimal implementation per cycle". "Refactoring is not part of the loop. It belongs to the review stage (see the `code-review` skill)." Asks the user to confirm seams first. No checklist or test-command instructions.
- **code-review**: `git rev-parse`, `git diff <fp>...HEAD`, `git log`; spawns **Standards** and **Spec** subagents "together, in the foreground"; presents them under `## Standards` / `## Spec`; "End with a one-line summary: total findings per axis, and the worst issue within each axis". Findings are free text; no count format is fixed.
- **grilling**: fixed round format, numbered: `❓ **Q1** - **<question title>**: <body>` then `➡️ <recommended answer>`, rounds separated by `---`; then "wait for the user's answers", i.e. the turn ends. Asked in assistant text, not `AskUserQuestion`.
- **wayfinder**: grilling/domain-modeling for grilling tickets; research tickets via subagents; tracker writes via `gh`. **to-tickets**: `gh issue create` per ticket (GitHub polling covers both).

None of these skills calls `TodoWrite`/`TaskCreate` explicitly; any checklist is the model's own habit.

## Verified hook facts (experiment)

1. **Subagent tool calls fire the session's hooks with `agent_id` / `agent_type`** (docs: hooks "Hooks from settings files, managed policy settings, and plugins also run inside subagents"). Seen: `{"agent_id": "a64f6deda9ac98f33", "agent_type": "general-purpose", "hook_event_name": "PreToolUse", "tool_name": "Bash", …}`.
2. **Agent → agent_id join.** `PostToolUse(Agent)` in the parent returns `tool_response.agentId`, equal to the `agent_id` on `SubagentStart` and every subagent event. For a background launch it arrives at once: `{"isAsync": true, "status": "async_launched", "agentId": "a748acb5263e72c74", "description": "Ticket #42 step", "prompt": "You are implementing ticket #42. …"}`. `SubagentStart` arrived before `PostToolUse(Agent)` in one run and after it in another, so the server must join on the id, not on order. `tool_input` also carries `"isolation": "worktree"` when passed.
3. **Worktree subagents report the worktree as `cwd`.** With `isolation: "worktree"`, `SubagentStart` and every subagent tool event had `"cwd": ".../.claude/worktrees/agent-a748acb5263e72c74"` (the worktree is named `agent-<agentId>`), while main-session events kept the parent cwd. The hook script can resolve the branch with `git -C "$cwd" branch --show-current`. The worktree was removed after the subagent finished with no changes.
4. **Bash outcome is split across two events.** Exit 0 → `PostToolUse` with `tool_response: {stdout, stderr, interrupted, isImage, noOutputExpected}` (no exit code field). Non-zero → `PostToolUseFailure` with `"error": "Exit code 3"`, `"is_interrupt": false`, `duration_ms`. Docs: key on the `Exit code N` first line; rest is display text, may be middle-truncated.
5. **Task tools are off by default on current models.** On haiku-5-5 (and in this research session, Opus 5.5) `ToolSearch select:TaskCreate` found nothing. Docs (tools-reference "Task tool availability"): on by default only on Opus 4.7, Sonnet 4.6, Haiku 4.5 and earlier; opt in with `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`; `CLAUDE_CODE_ENABLE_TASKS=0` swaps the four Task tools for `TodoWrite`. Background and cloud sessions always have them.
6. **Background subagents lose Task\* but keep TodoWrite.** With `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`, the main session had `TaskCreate`/`TaskUpdate`, but a background subagent did not (docs sub-agents: a background subagent keeps only `Read, Grep, …, TodoWrite, Skill, …`). With `CLAUDE_CODE_ENABLE_TASKS=0` added, a background subagent's `TodoWrite` fired `PreToolUse`/`PostToolUse` with `agent_id` and `tool_response: {"oldTodos": [], "newTodos": [{"content": "Subagent item", "status": "in_progress", "activeForm": "Working on subagent item"}]}`.
7. **Task tool payloads (main session).** `TaskCreated`: `task_id`, `task_subject`, `task_description` (docs: `agent_id` when in a subagent, v2.1.290+). `PostToolUse(TaskUpdate)`: `tool_input {taskId, status}`, `tool_response {statusChange: {from, to}}`. `TaskCompleted` fires on `completed`. There is no TaskUpdated event, so in-progress changes come only from `PostToolUse(TaskUpdate)`.
8. **Assistant text reaches hooks.** `Stop.last_assistant_message` and `MessageDisplay.delta` both held `❓ **Q1** - **Pick a name**: what name? ➡️ Bob` verbatim. `MessageDisplay` fired only for main-session messages, never with an `agent_id`; subagent text arrives only via `SubagentStop.last_assistant_message` / `PostToolUse(Agent).tool_response.content`. `Stop` also carries `background_tasks` listing running subagents (`{"id", "type": "subagent", "status": "running", "description", "agent_type"}`).
9. **A plugin cannot set env vars.** Plugin `settings.json` honours only `agent` and `subagentStatusLine` (plugins-reference). So the Task-tool env vars must go into the user's `~/.claude/settings.json` `env` (or shell) at Factory install.

## Per field

### 1. Phase (Exploring / Red / Green / Refactor / Reviewing / Committed / Merged)

- **Source:** server-side inference per Step (`session_id` + `agent_id`) from verified signals:
  - **Exploring:** Step started (`SubagentStart`, or `Skill(tdd)`/`Skill(implement)` start), no test-file edit yet.
  - **Red:** a test file edited (`PostToolUse` `Edit|Write|MultiEdit`, `tool_input.file_path` matching test globs: `test_*.py`, `*_test.*`, `*.test.*`, `*.spec.*`, `tests/`, `__tests__/`) and the next test run fails (field 3).
  - **Green:** a source (non-test) file edited, then a test run passes.
  - **Refactor:** source edits after Green with no new test edit and tests still passing. *Weakest phase*: tdd explicitly puts refactoring in the review stage, so in Matt's flow it mostly happens while fixing code-review findings.
  - **Reviewing:** `PreToolUse(Skill)` with `tool_input.skill` ending `code-review` in that agent/session. Note: implement-spec runs code-review once on the integration branch, not per Step, so per-Step Reviewing is only reached in `implement` Jobs.
  - **Committed:** `PostToolUse(Bash)` whose command contains `git commit` (exit 0).
  - **Merged:** merger subagent's `git merge` into the integration branch (Bash, exit 0), or the PR merged (GitHub polling) for single-Ticket Jobs.
- **Confidence:** each signal **verified**; mapping signals to Phase **inferred**. Bash-driven edits (`sed -i`, heredocs) skip `Edit|Write`; docs offer `tool_response.bashEditDiff` (beta, only in auto/bypass mode or with `bashEditDiffEnabled`) or a `git status --porcelain` in the hook to catch them.
- **Fallback:** inject (SessionStart / `SubagentStart` `additionalContext`) "run `factory phase red|green|refactor` when you change phase". Model compliance is unproven, so treat self-report as an override, not the primary. If neither yields a signal: Phase unknown.
- **Transcript peek cost:** nothing gained; every signal is in the hook payloads.

### 2. Spec Job Steps (subagent / worktree → Ticket)

- **Source:** in the Spec Job's main session, `PostToolUse(Agent)`:
  - `tool_response.agentId` → the Step's key (joins to all subagent events via `agent_id`).
  - `tool_input.description` / `tool_input.prompt` → regex the Ticket ref (`#\d+`, issue URL), checked against the Spec's Tickets from GitHub polling.
  - `tool_input.isolation == "worktree"` → implementer; the subagent's event `cwd` = worktree path; branch via `git -C cwd`.
  - Implementer vs merger vs exploration subagent: prompt keywords ("merge"), or whether it calls `Skill(tdd)`.
- **Confidence:** join, cwd and worktree **verified**; that implement-spec puts the Ticket ref in the prompt is **inferred** from "communicate primarily through context pointers: to the spec, tickets…". The implementer usually runs `gh issue view <n>` early (Bash, carries `agent_id`), a second corroborating signal (**inferred**).
- **Fallback:** `SubagentStart` `additionalContext` (**documented**: "added to the subagent's context at the start of its conversation") telling it: "if you are implementing a Ticket, run `factory step --ticket <n> --role implementer|merger`". Else: Step row with Ticket unknown.
- **Transcript peek cost:** `<session>/subagents/agent-<id>.meta.json` holds `agentType`, `worktreePath`, `worktreeBranch`, `description` (#5). Cheap, one small file, but adds nothing over `PostToolUse(Agent)` + `cwd`.

### 3. Test pass/fail pulse

- **Source:** `PreToolUse`/`PostToolUse`/`PostToolUseFailure` matcher `Bash`; `tool_input.command` classified as a test run; pass = `PostToolUse`, fail = `PostToolUseFailure` whose `error` starts `Exit code N` (**verified**). Pair Pre/Post by `tool_use_id`.
- **Telling the test command apart (inferred):**
  - Default patterns: `pytest`, `python -m pytest`, `npm|pnpm|yarn|bun (run )?test`, `vitest`, `jest`, `go test`, `cargo test`, `mvn test`, `gradle test`, `dotnet test`, `rspec`, `uv run pytest`, `make test`.
  - Per Tracked repo override: test-command patterns stored with the `.factory/` marker (or read from `package.json` `scripts.test` / `pyproject` at `/factory on`).
  - Single-file vs full suite (implement runs both): a path argument means single file.
- **Pitfalls:** `npm test 2>&1 | tail -20` exits with `tail`'s status, so failures read as passes; `&&` chains mix commands; `run_in_background: true` returns before the result. Mitigation: also parse `stdout`/`error` for the runner summary (`N failed`, `FAILED`, `passed`); mark background runs unknown.
- **Fallback:** self-report `factory test pass|fail [--count]` via injected context; else no pulse.
- **Transcript peek cost:** none; the tool result in the transcript is the same text as `stdout`/`error`.

### 4. Agent's live checklist

- **Source:** `PostToolUse(TodoWrite)` `tool_response.newTodos` (whole list with `content`, `status`, `activeForm` each call); or `TaskCreated` + `PostToolUse(TaskUpdate)` (`statusChange`) when the Task tools are active. Both carry `agent_id` inside subagents (**verified** for TodoWrite in a background subagent; `TaskCreated.agent_id` **documented**, v2.1.290+).
- **The catch (verified):** on current models neither tool exists by default, so most sessions produce **no checklist at all**. implement-spec's background implementers would lose `TaskCreate` even with the opt-in; only `TodoWrite` survives there.
- **Recommendation:** the Factory installer writes `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` and `CLAUDE_CODE_ENABLE_TASKS=0` into user settings `env`, giving `TodoWrite` uniformly in main sessions and background subagents and one payload shape to parse. Cost: extra tool definitions and reminders in context (docs say this is why newer models drop them); this is a change to the session, not to the skills.
- **Fallback:** no opt-in → checklist unknown. (Self-reporting a checklist duplicates TodoWrite; not worth it.)
- **Transcript peek cost:** none; same content.

### 5. Review findings count

- **Source:** self-report. `PostToolUse(Skill)` with `tool_input.skill` matching `code-review` returns `additionalContext`: "after the two-axis summary, run `factory review --standards <n> --spec <m> [--worst-standards "…" --worst-spec "…"]`". Confidence **inferred**: the `additionalContext` path is documented and the Skill trigger verified in #5, but the numbers are the model's own count.
- **Hook-only fallback:** code-review's final message ends with "a one-line summary: total findings per axis". It lands in the main thread, so `MessageDisplay.delta` sees it even mid-turn (implement continues to commit afterwards), and `Stop.last_assistant_message` if it ends the turn. Also `PostToolUse(Agent).tool_response.content` for the Standards and Spec subagents (foreground, so `completed` with `content`). No fixed format → regex on the summary line is fragile. Else unknown.
- **Transcript peek cost:** none beyond the payloads above.

### 6. Wayfinder grilling round question titles

- **Source:** `Stop.last_assistant_message` (a grilling round ends the turn, waiting on the user) → regex `❓ \*\*Q(\d+)\*\* - \*\*(.+?)\*\*:`. `MessageDisplay` (main session only, display-only, blocks rendering until the hook returns, so keep it async/fast) gives the same text live. Detect grilling as active via `Skill` / `UserPromptExpansion` for `grilling` (or `grill-with-docs`).
- **Confidence:** text delivery **verified**; the regex relies on the model following grilling's template (**inferred**, usually true since the template is explicit).
- **Fallback:** questions shown as "round N, titles unknown"; optional self-report `factory round --q "<title>"…` via injected context.
- **Transcript peek cost:** none; `last_assistant_message` exists precisely so hooks don't read the lagging transcript (hooks docs).

## Transcript-peek cost summary

| Field | What a peek would add | Cost |
| :- | :- | :- |
| Phase | nothing | n/a |
| Spec Job Steps | `agent-<id>.meta.json` (`worktreePath`, `worktreeBranch`, `description`) | small file read per Step; redundant |
| Test pulse | nothing | n/a |
| Checklist | nothing (no tools → nothing written either) | n/a |
| Review count | nothing beyond subagent final text | n/a |
| Grilling titles | nothing | n/a |

Keeping transcripts ruled out costs nothing for these six fields.

## Open points for later tickets

- Whether to set the Task-tool env vars at install (context cost vs a checklist on the dashboard).
- Test-command patterns per repo: auto-detect at `/factory on` or ask.
- Whether self-report CLI calls are complied with reliably enough to override inferred Phase: needs a prototype run of `implement` with the injected instruction.
