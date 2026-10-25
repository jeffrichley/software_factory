# Survey: autonomous coding agents

Answers #3 (child of Map #1). Researched 2026-10-25 against vendor docs. Most doc pages carry no dates; "current" means live on that day.

## Question

What can Devin, OpenHands, Factory.ai, GitHub Copilot coding agent and Sweep do, and how do they work: how work enters, how it is split, how agents hand off, how humans are asked for input, how work lands, how progress is shown? Which ideas fit a Factory that runs Matt Pocock's skills locally?

## Short answer

All five follow one pattern: **an issue (or a chat mention) is the trigger, one agent session owns one Work item in an isolated workspace, a PR is the only landing surface, and a per-session log/timeline is the progress view.** They differ in how large work is split (Devin: coordinator plus child sessions; Factory.ai: Missions with milestones and validator workers) and in how they gate risky actions (Factory.ai autonomy levels, OpenHands confirmation policies). Every one runs in the cloud, so the Factory borrows their *protocol* (triggers, states, reporting back to the issue), not their execution model.

## Per-agent findings

### GitHub Copilot coding agent ("Copilot cloud agent")

- **Entry:** issues, Agents panel/tab, Copilot Chat, dashboard, failing Actions runs, security campaigns, and automations (scheduled or on events such as "issue opened"). [about][gh-about], [create-a-pr][gh-pr]
- **Issue flow:** assign the issue to Copilot; it adds a 👀 reaction, creates a `copilot/` branch and a draft PR linked to the issue. It sees only the issue title, body and comments at assignment time; later guidance goes on the PR. (Search snippets of GitHub docs and Microsoft Learn, not read in full: [troubleshoot][gh-ts], [MS Learn][ms-learn].)
- **Human input:** `@copilot` comments on the PR from users with write access; Copilot pushes new commits to the same branch. It ignores merged/closed PRs. When done it "opens a pull request and adds you as a reviewer." [overview][gh-overview]
- **Limits:** one repo, one branch, one PR per task; 59-minute session cap (`timeout-minutes` in `copilot-setup-steps.yml`). [about][gh-about]
- **Progress:** session logs (reasoning, files read, changes) linked from a "Copilot started work" event in the PR timeline. [about][gh-about], [overview][gh-overview]
- **Extensibility:** custom instructions, custom agents, agent skills, hooks, MCP. [about][gh-about]

### Devin (Cognition)

- **Entry:** Slack/Teams mention, Linear/Jira tickets, web app, API, Devin CLI (local) with `/handoff` to cloud. [docs][devin-home]
- **Planning:** "Ask Devin" plan mode breaks a task down and writes a context-rich prompt that seeds the session; the session's status shows back in the conversation. [ask-devin][devin-ask]
- **Splitting:** *Managed Devins*: a coordinator launches child sessions, each in its own VM, each with its own prompt, playbook, tags and ACU (cost) limit. It splits work into packages "that won't conflict", monitors, resolves conflicts and compiles results. Children wake the coordinator when they "finish or need input"; it can wait on all in one MCP call, message, sleep or kill them. Child launch is auto-approved unless you turn that off. [advanced][devin-adv]
- **Handoff from other agents:** an open-source Devin Handoff plugin lets any local agent (e.g. Claude Code) package repo, branch, `git diff HEAD` (≤100KB), hypotheses and partial fixes into a cloud session and return its URL. [handoff][devin-handoff]
- **Landing:** PRs follow the repo's PR template; author can be Devin or the user. Devin auto-responds to comments on PRs its live session owns; a `/devin` comment starts or redirects a session. Branch protection recommended so checks pass before merge. [GitHub][devin-gh]
- **Progress:** Progress tab unifying shell, edits and browser; side chats (read-only questions without interrupting); pause and take over the IDE. [session tools][devin-tools]

### OpenHands (All Hands)

- **Architecture (2026):** Agent Canvas (browser client), Software Agent SDK + Agent Server (REST/WebSocket), Sandbox Server, Automation Server (scheduled and event-driven); previous backend archived as "Legacy". [docs][oh-home]
- **Entry:** `openhands` label on an issue or an `@openhands` comment; `@openhands` in PR comments; Slack, Jira; automations. [GitHub][oh-gh]
- **Reporting back to the issue:** it comments "working on it" with a link to the live conversation, opens a PR only if it judges the issue resolved, then comments a summary plus PR link. [GitHub][oh-gh]
- **Readiness gate (their own repos):** a bot applies type labels; a workflow checks the issue body against type-specific criteria (repro steps, acceptance-criteria checklist) and applies `ready-for-dev`. PR descriptions are validated: `HUMAN:` note first, then `AGENT:`, required sections, and the PR must reference a `ready-for-dev` issue. [issue lifecycle][oh-life]
- **Human input:** confirmation policies `AlwaysConfirm` / `NeverConfirm` / `ConfirmRisky` (a security analyzer rates actions LOW/MEDIUM/HIGH/UNKNOWN). A paused agent has `execution_status=WAITING_FOR_CONFIRMATION`; rejecting with a reason lets it try another approach. [security][oh-sec]
- **Splitting:** a Task tool set and file-based sub-agents in the SDK. [llms.txt][oh-llms]

### Factory.ai (Droids)

- **Entry:** Factory App (desktop), Droid CLI, headless `droid exec`, SDK, IDE; delegation from Slack and Linear (assign the issue to Factory or `@Factory`). [home][fa-home], [Linear][fa-linear]
- **Linear flow:** it runs on a remote computer under a service account, moves the issue to In Progress, posts progress in Linear's agent session (Stop button supported), is "instructed to open a pull request and return its URL", and attaches the PR to the issue. [Linear][fa-linear]
- **Splitting, Missions:** `/missions` starts a planning *conversation*: Droid "will push back, ask questions, and iterate with you until the plan is solid", producing features grouped into milestones. You approve the plan. An orchestrator (you can talk to it) runs feature workers (about one per feature) and validator workers at the end of each milestone (QA against the running app); failed validation adds fix features. Mission Control shows progress. Run estimate ≈ #features + 2 × #milestones. [missions][fa-missions], [planning][fa-plan]
- **Autonomy levels:** Off / Low / Medium / High, each command's risk compared to the level; command policy `allow` / `ask` / `block` overrides; "allow always" raises the level. [auto-run][fa-auto]
- **Hooks:** PreToolUse, PostToolUse, UserPromptSubmit, Notification, Stop, SubagentStop, PreCompact, SessionStart, SessionEnd; plugins use `${CLAUDE_PLUGIN_ROOT}`. This mirrors Claude Code's hook model. [hooks][fa-hooks]
- **Worktrees:** the App makes a new branch per worktree; ephemeral worktrees are auto-cleaned past a limit (default 15) but skipped if they have uncommitted changes or an open PR; cleanup removes the checkout, never the branch. [worktrees][fa-wt]
- **App:** sessions are filtered and grouped across projects *and machines*; inline diff comments go back to the Droid. [app][fa-app]

### Sweep

- **Status:** the README now says "We're now building an AI coding assistant for JetBrains"; the GitHub issue-to-PR bot is legacy (no deprecation date found). [repo][sweep]
- **Old flow:** an issue titled `Sweep: ...` at creation, or a `Sweep` label on an existing issue, triggered plan, then PR; replying "Sweep: ..." on the issue/PR made it retry. [PyPI 3.1.5][sweep-pypi], [PyPI 0.5.2][sweep-pypi05]
- Takeaway: the single-shot issue-to-PR bot did not survive as a product; the survivors added iteration loops, planning and human steering.

## Cross-cutting comparison

| Concern | Common pattern | Notable variant |
|---|---|---|
| Work enters | Assign issue / label / `@agent` mention | Copilot automations on events; Devin handoff from local agents |
| Split | One session per Work item | Devin coordinator + children; Factory.ai Missions milestones |
| Handoff | Child reports back to coordinator | Devin: wake-on-finish-or-needs-input |
| Human input | Comments on the PR; pause/approve gates | Factory.ai autonomy levels; OpenHands `WAITING_FOR_CONFIRMATION` |
| Lands | One PR per task, human merges | OpenHands only opens a PR if resolved; PR template validation |
| Progress | Per-session log linked from the issue/PR | Factory.ai groups sessions across machines; Linear agent session |

## Ideas that fit the Factory

Constraints from Map #1: local only, skills unmodified, a PR the human merges, Needs you / Done.

1. **Report back on the Work item.** On Job launch, comment on the Ticket/Spec issue with the Job and its dashboard link; on Done, comment a summary plus the PR link (OpenHands, Copilot, Factory.ai Linear). This is cheap, done from hooks, and needs no change to the skills.
2. **Needs you as an explicit state with a reason.** Model it like OpenHands' `WAITING_FOR_CONFIRMATION` and Devin's "needs input": the Job records *why* (question, HITL, permission, escalation). Claude Code `Notification`/`Stop` hooks are the same events Factory.ai exposes.
3. **Coordinator wake-up for Spec Jobs.** Devin's children wake the coordinator on finish-or-needs-input; that is exactly what the Factory needs to roll Steps up into a Spec Job's state. A Step needing you makes the Job need you.
4. **Readiness gate for automatic pickup** (an unresolved item on the Map). Pick up only `ready-for-agent` issues that pass a body check (acceptance criteria present), as OpenHands' `ready-for-dev` does, with a concurrency cap.
5. **Per-Job cost/time limits.** Devin's per-child ACU limit and Copilot's 59-minute cap are evidence for the Map's "retries, timeouts, cost tracking" item.
6. **Worktree hygiene rules.** Adopt Factory.ai's rule: auto-clean old Job worktrees, but never one with uncommitted changes or an open PR, and never delete the branch.
7. **Group the dashboard by machine as well as by repo** (Factory App), which supports the "multiple machines" item.
8. **PR iteration via comments.** `@copilot` / `/devin` comments route to the live session. A Factory equivalent (a PR comment resumes the Job) is possible but needs a listener. Defer it.

**Do not fit:** cloud VMs per Job (out of scope), auto-approved child launches without human sight, and vendor-specific planning (Missions/Ask Devin), since `wayfinder`/`to-spec`/`to-tickets` already cover planning.

## Sources

All URLs were accessed 2026-10-25. Note: docs.factory.ai now redirects to docs.factory.com.

- GitHub Copilot: [about][gh-about] · [create a PR][gh-pr] · [overview][gh-overview] · [troubleshoot][gh-ts] · [MS Learn][ms-learn]
- Devin: [home][devin-home] · [Ask Devin][devin-ask] · [advanced capabilities][devin-adv] · [handoff][devin-handoff] · [GitHub][devin-gh] · [session tools][devin-tools]
- OpenHands: [home][oh-home] · [GitHub integration][oh-gh] · [issue lifecycle][oh-life] · [security][oh-sec] · [llms.txt][oh-llms]
- Factory.ai: [home][fa-home] · [Linear][fa-linear] · [Missions][fa-missions] · [planning][fa-plan] · [autonomy][fa-auto] · [hooks][fa-hooks] · [worktrees][fa-wt] · [app][fa-app]
- Sweep: [repo][sweep] · [PyPI 3.1.5][sweep-pypi] · [PyPI 0.5.2][sweep-pypi05]

[gh-about]: https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent
[gh-pr]: https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-a-pr
[gh-overview]: https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/overview
[gh-ts]: https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/use-copilot-agents/cloud-agent/troubleshoot-cloud-agent
[ms-learn]: https://learn.microsoft.com/en-us/training/modules/github-copilot-code-agent/3-assign-track-troubleshoot-copilot-code-agent-tasks
[devin-home]: https://docs.devin.ai/
[devin-ask]: https://docs.devin.ai/work-with-devin/ask-devin
[devin-adv]: https://docs.devin.ai/work-with-devin/advanced-capabilities
[devin-handoff]: https://docs.devin.ai/work-with-devin/devin-handoff
[devin-gh]: https://docs.devin.ai/integrations/gh
[devin-tools]: https://docs.devin.ai/work-with-devin/devin-session-tools
[oh-home]: https://docs.openhands.dev/
[oh-gh]: https://docs.openhands.dev/openhands/usage/cloud/github-installation
[oh-life]: https://docs.openhands.dev/overview/issue-lifecycle
[oh-sec]: https://docs.openhands.dev/sdk/guides/security
[oh-llms]: https://docs.openhands.dev/llms.txt
[fa-home]: https://docs.factory.com/
[fa-linear]: https://docs.factory.com/delegations/linear
[fa-missions]: https://docs.factory.com/docs/missions/overview
[fa-plan]: https://docs.factory.com/missions/planning
[fa-auto]: https://docs.factory.com/autonomy-and-safety/auto-run
[fa-hooks]: https://docs.factory.com/harness/hooks
[fa-wt]: https://docs.factory.com/factory-app/worktrees
[fa-app]: https://docs.factory.com/docs/factory-app/overview
[sweep]: https://github.com/sweepai/sweep
[sweep-pypi]: https://pypi.org/project/sweepai/3.1.5
[sweep-pypi05]: https://pypi.org/project/sweepai/0.5.2
