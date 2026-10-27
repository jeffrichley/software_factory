# software_factory

## Agent skills

### Issue tracker

Issues live in GitHub Issues (jeffrichley/software_factory), via `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md` + `docs/adr/`. See `docs/agents/domain.md`.

## Subagent worktrees

Agents can edit files only under paths with an `Edit(...)` allow rule in `.claude/settings.json`: the repo, `.claude/worktrees/`, and `/mnt/e/workspaces/ai/tools/sf-worktrees/`. Auto mode otherwise fails every in-repo edit with "classifier gave no verdict" (anthropics/claude-code#102351). Put a subagent's worktree under one of those paths and brief it with the worktree's absolute path. A new allow rule takes effect only after the session restarts.
