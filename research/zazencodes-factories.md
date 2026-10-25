# zazencodes software factories v1 and v2: what to borrow, what to avoid

Research for #2 (map #1). Question: what do zazencodes' factories v1 and v2 do,
and what should **the Factory** borrow or avoid? Focus is what v2 adds: taking
work from GitHub issues, merging through PRs, and how its jobs, verdicts,
escalations and dashboard compare with v1.

## Sources

- **v2:** `src/software-factory-claude-code-v2/` in
  [zazencodes/zazencodes-season-3](https://github.com/zazencodes/zazencodes-season-3/tree/main/src/software-factory-claude-code-v2),
  HEAD `3e45f54` (2026-10-23). The folder has one commit, `d623a3e` "Add
  software factory v2" (2026-10-22). Read only; nothing run.
- **v1:** `src/software-factory-claude-code/` in the same repo, already
  analysed in `transcripts/zazencodes-software-factory-analysis.md` (git-ignored,
  driver's machine). v1 claims below come from there and aren't re-derived.
- Line refs are `file:line` within the v2 folder.

## Caveat: v2's prompts aren't published

v2's README (`README.md` "What's in here") and `INSTALL.md:29-37` list
`.claude/skills/factory/SKILL.md` and eight agents (`intake`, `spec-writer`,
`builder`, four reviewers, `approver`). **None of them is in the repo.** The
tree for the v2 folder has no `.claude/` (v1's does), the GitHub commits API
shows no commit ever touching `src/software-factory-claude-code-v2/.claude`,
and `raw.githubusercontent.com/.../v2/.claude/skills/factory/SKILL.md` returns
404 while `.../v2/factory/bin/job` returns 200. So `INSTALL.md`'s curl install
would fail on the skill and agents.

What *is* published: the deterministic spine (`factory/bin/job`, `gate`,
`route`), `config.json`, `checks.sh`, `dashboard.html`, `DESIGN.md`,
`BUILD_PROMPT.md` (the prompt that builds v2 from v1), and four example jobs.
Agent behaviour below is inferred from `DESIGN.md`, `BUILD_PROMPT.md`, the
spine's file contracts and the example outputs, not from the prompts.

## What v1 is (summary)

One `/factory <feature>` skill turns the session into an orchestrator for one
job; seven subagents (spec-writer, builder, security/ux/ui/code reviewers,
approver) hand off through files in `factory/jobs/<id>/`, each with a
first-line sentinel (`STATUS:`, `VERDICT:`, `APPROVE|ESCALATE`). A named
builder is resumed with `SendMessage` across ≤3 review rounds. APPROVE merges
locally with `git merge --no-ff` into `main` (needs a clean main checkout);
ESCALATE parks the job as `needs-human` for `/factory approve|rework`. Intake is
a hand-typed feature or `backlog.md`. No hooks, no scripts, no PRs; the state
machine and every guardrail are prose. A static HTML kanban polls `job.json`.

## What v2 adds

`DESIGN.md:135-142` ("What changed from v1") is the author's own diff. Checked
against the code:

### 1. GitHub issues are the queue

- Only open issues labelled `factory` run (`config.json` `labels.queue`). The
  label is the trust boundary: only triage/write users can add labels
  (`DESIGN.md:120-121`).
- `job queue` (`factory/bin/job:518-551`) classifies every labelled issue as
  `new`, `resume`, `wait` or `skip`. It also auto-advances a `needs-human` job
  to `merged` when its PR was merged on GitHub (`:522-524`): merging is the
  approval.
- `job create <issue>` (`:491-515`) refuses closed, unlabelled or
  already-jobbed issues, allocates `NNN-slug`, and writes `issue.md`.
- **Prompt-injection handling** (`:178-203`): `issue.md` quotes the body and
  comments line by line (`> `) under a header saying they're data, not
  instructions; only comments from the issue author and the operator are
  kept. Intake, the first reader, has no shell (`DESIGN.md:123-124`).
- Triggered manually: `/factory run` drains the queue. No Actions, no schedule
  (`DESIGN.md:43-47`).

### 2. Intake agent at the door

New agent on Fable (once per issue). Writes `intake.md` with a header
`DECISION: ACCEPT|NEEDS-INFO|REJECT`, `RISK: low|medium|high`,
`SURFACES: ui, security|none`, `RESCOPED: yes|no`, then `## Scope` / `## Why`
(see `examples/jobs/*/intake.md`; parsed by `header()` at `job:141-149`).

- **ACCEPT** may cut scope: example 003 cut "multiply, divide, power, sqrt,
  log, trig, parser and a REPL" to three functions.
- **NEEDS-INFO** comments on the issue, adds `factory:needs-info`, parks the
  job; `job queue` resumes it when the author or operator replies after the
  factory's last marked comment (`:206-215`). Questions get answered *before*
  a spec exists, so the spec-writer never stalls (`DESIGN.md:57-62`).
- **REJECT** comments why and removes the `factory` label (example 005
  rejected a crypto-miner request as cryptojacking).

### 3. Risk routing by script

`factory/bin/route` maps intake's risk + surfaces through `config.json`
`routing` / `surface_reviewers` to a builder model and reviewer set
(`route:340-363`). Only the code reviewer always runs; ux+ui on `ui`, security
on `security`. Low risk, no UI = one Haiku reviewer. v1 always ran all four.

### 4. A deterministic spine (the biggest change)

`factory/bin/job` is "the only writer of job.json" and "refuses illegal moves"
(`job:1-7`).

- `TRANSITIONS` (`job:40-50`): `intake → needs-info|rejected|spec`,
  `spec → build`, `build → gate|needs-human`, `gate → review|build|needs-human`,
  `review → approve|build|needs-human`, `approve → merging|needs-human`,
  `merging → merged|needs-human`, `needs-human → build|merged`.
- Each transition **checks the files that justify it** (`advance`,
  `job:352-480`): e.g. `build → gate` needs `STATUS: READY`, a clean worktree,
  ≥1 commit, the branch pushed and exactly one open PR; `gate → review` needs
  `GATE: PASS` *for the current HEAD commit*; `review → approve` needs every
  routed review present with a valid `VERDICT:` and none `CHANGES`; round
  limits are enforced; `approve → merging` needs `decision.md` = `APPROVE`.
- Transitions own their GitHub side effects (comments with a
  `<!-- factory -->` marker, labels, worktree add/remove, PR ready, merge), so
  the orchestrator "never improvises them".
- Per-job `fcntl.flock` lock and atomic write-then-rename of `job.json`
  (`job:104-119`).

Still prose: *when* to call the spine, spawning agents, and the agents' own
rules live in the unpublished `SKILL.md`. The spine stops illegal states; it
doesn't drive the loop.

### 5. Deterministic gate before review and before merge

`factory/bin/gate` runs the **main checkout's** `checks.sh` in the job's
worktree, so a branch can't edit the checks that judge it, and fails any
branch that modifies or deletes a file matching `protected_paths` (new files
are fine) (`gate:376-379`, `:408-449`). Writes `round-N/checks.md` with
`GATE: PASS|FAIL` + `COMMIT: <sha>`. A failing gate sends the log straight to
the builder; no reviewer runs. Reviewers then judge only what scripts can't
(`DESIGN.md:89-90`). `gate --hook` is a builder `SubagentStop` hook: runs the
checks once and exits 2 to push the builder back, as a nudge; the gate still
decides (`gate:452-467`).

### 6. Exit is a PR

Builder pushes `factory/<job-id>` and opens a draft PR "Closes #n" in round 1
(enforced at `build → gate`, `job:394-402`).

- **APPROVE** → `job merge` (`job:554-589`): merge `origin/<base>` into the
  branch, gate again (`merge-checks.md`), push, mark ready, `gh pr merge
  --<method>`. Conflict or failed gate → escalate. Main checkout never touched;
  branch protection and required checks apply.
- **ESCALATE** → PR marked ready, decision posted as a PR comment, issue
  labelled `factory:needs-human` (`job:464-472`). The human approves by merging
  on GitHub, or comments and runs `/factory rework <n>`, which collects only
  the operator's PR/review/inline comments since the escalation into
  `rework-k.md` and grants a fresh `max_rounds` (`job:592-623`, `:460`).

Note: the approver still **auto-merges** what it approves. That is v2's
default, not "a PR the human merges".

### 7. One orchestrator, many jobs, resumable

One session runs `/factory run`, starts up to `concurrency` (default 3) jobs
and spawns every agent as a background subagent; agents and scripts reply
with one line so its context stays small (`DESIGN.md:49-55`). Since all state
is in `factory/jobs/`, a fresh `/factory run` resumes every job after a crash
or compaction (`DESIGN.md:115-117`). v1 needed one session per job and had no
resume.

### 8. Cost and time per job

`cost_usd()` (`job:246-284`) globs
`~/.claude/projects/<project>/*/subagents/agent-*.jsonl`, keeps transcripts
whose first prompt contains `Job folder: <path>/`, dedupes usage by message id,
and prices it from `prices_usd_per_mtok`. API-equivalent, excludes the
orchestrator's own tokens, and depends on an **undocumented transcript format**
(`DESIGN.md:107-113` says so). `started`/`ended` give time. Shown on cards and
in `job summary`.

## Jobs, verdicts, escalations, dashboard: v1 vs v2

| | v1 | v2 |
|---|---|---|
| Trigger | `/factory <feature>`, `backlog.md` | `factory` label on an issue; `/factory run` drains; `/factory issue <n>`; `/factory <feature>` files an issue first |
| Job unit | one feature, one session | one issue, one PR; many per session |
| `job.json` writer | orchestrator (LLM) | `factory/bin/job` only, with legal-transition checks |
| Stages | spec, build, review, approve, merged, needs-human | + intake, needs-info, gate, merging, rejected |
| Verdict formats | `STATUS:` / `VERDICT:` / `APPROVE\|ESCALATE` first lines | same, plus `DECISION/RISK/SURFACES/RESCOPED` header and `GATE: PASS\|FAIL` + `COMMIT:` |
| Who validates verdicts | nobody (prose) | spine parses them; invalid first line → `invalid`, transition refused |
| Tests run by | builder + code reviewer (LLM, could skip) | `checks.sh` gate before review and before merge |
| Escalation sources | approver ESCALATE, BLOCKED, rounds exhausted, busy checkout, merge fail | approver ESCALATE, BLOCKED, gate fails in last round, reviews exhausted, merge conflict, gate fails after sync, `gh` merge error; spine writes `decision.md` for the non-approver ones (`job:324-326`) |
| Where escalation surfaces | `needs-human` column only | PR comment + `factory:needs-human` label + dashboard column |
| Approve / rework | `/factory approve`, `/factory rework <id> <note>` | merge the PR; `/factory rework <n>` reads your PR comments |
| Merge | local `git merge --no-ff`, needs clean main | `gh pr merge` after sync + re-gate |
| Cost | none | per job, from transcripts |
| Resume | none | `/factory run` resumes from files |

**Dashboard** (`factory/dashboard.html`, 656 lines, vanilla JS): same
mechanism as v1, still polling every 2 s (`:278`) and parsing
`python3 -m http.server` directory listings to find jobs (`:440-451`) and
files (`:455`). Columns (`:279-287`): Intake (incl. needs-info), Spec, Build
(build+gate), Review, Approve (approve+merging), **Needs human** ("your call"
flag), **Done** (merged+rejected). Each card: issue and PR links, risk,
builder model, cost, elapsed time, and per round a gate chip followed by only
the routed reviewers' chips. Header totals: running count and total cost.
Drawer renders every file in pipeline order. Still read-only: no buttons.

## What the examples show

Four jobs from a sandbox calculator repo, all agents forced to Haiku with
`concurrency: 2` (`README.md` "The example jobs"); job.json confirms
`builder: haiku` even though `config.json` routing says Sonnet.

- **001** (low, no UI): one Haiku reviewer, APPROVE, auto-merged via PR #6.
  2 min, $0.13. The approver ran two ACs itself.
- **002** (low, `ui`): code+ux+ui reviewers, APPROVE, merged. $0.14.
- **003**: intake rescoped, but told the builder to put tests in
  `tests/test_calc.py`, which the installer had listed in `protected_paths`.
  Round 1 gate FAIL (protected file modified); round 2 builder moved the tests
  to a new file, gate PASS, code review CHANGES ("silent departure from the
  spec ... get a decision from the user"); round 3 builder `STATUS: BLOCKED`
  with an (a)/(b) choice → needs-human. Good escalation trail, but it exposes
  a gap: intake and spec-writer don't seem to know `protected_paths`. Its
  recorded cost ($0.03 over three rounds) is lower than 001's single round,
  which suggests the transcript-based cost can under-count.
- **005**: REJECT at intake, 17 s, no worktree work.

## Fit with the Factory

The Factory's constraints (map #1): Matt Pocock's skills run unmodified; the
Factory wraps and observes them; work lands as a PR the human merges; local
only, cross-platform (WSL, PowerShell, macOS); one dashboard per machine with
**Needs you** / **Done**.

zazencodes is a *pipeline of its own agents*; the Factory is an *observer and
launcher around someone else's skills*. So its roles (intake, spec-writer,
builder, reviewers, approver) and their prompts are **not** things to adopt:
Matt's `to-spec`, `to-tickets`, `implement`, `implement-spec` already fill
those roles. What transfers is the plumbing.

### Borrow

1. **A deterministic state writer for Jobs.** One script owns the Job record,
   with a legal-transition table and checks that the evidence exists (PR
   open, branch pushed, commit matches). For the Factory: Job/Step state comes
   from hooks + `gh`, written by one module, never by the LLM.
2. **Issue label as the trust boundary** for future automatic pickup
   (`ready-for-agent` plays the role of `factory`), plus `job queue`'s
   `new/resume/wait/skip` classification and a `concurrency` cap.
3. **Issue text as quoted data** with author/operator-only comments, if the
   Factory ever feeds issue text to an agent itself.
4. **Resume from files**: every fact on disk, so a restarted dashboard or
   session rebuilds state.
5. **The PR is the approval surface**: escalation posts the question on the
   PR and labels the issue; "merged on GitHub" is detected and moves the Job
   to Done. Matches the Factory's "PR the human merges".
6. **Needs-you reasons as data**: v2 writes a `decision.md` with a specific
   question for every escalation, whatever its source. The Factory's Needs
   you card should carry the reason (question, HITL, permission prompt,
   escalation) and the exact action.
7. **Per-Job cost and time** by attributing subagent transcripts to a Job via
   a fixed marker in the prompt; label it API-equivalent. Fills the map's
   "cost tracking" fog, with the caveat below.
8. **Dashboard details**: a Needs human column before Done, issue/PR links on
   each card, per-round chips, elapsed time, diff-based re-render.
9. **Hooks as nudges, scripts as deciders**: the `SubagentStop` hook pattern
   (exit 2 with a reason, `stop_hook_active` guard) is a ready model for the
   map's "enforcement" fog.

### Avoid

1. **Auto-merge by an approver agent.** v2 merges what its approver likes; the
   Factory's rule is the human merges.
2. **Owning the pipeline's agents and stages.** v2's `stage` enum and
   `TRANSITIONS` encode zazencodes' pipeline. The Factory must observe
   whatever stages Matt's skills go through, so Steps should be discovered,
   not hard-coded.
3. **POSIX-only plumbing**: `fcntl.flock` (`job:22,111`) doesn't exist on
   native Windows; `checks.sh`/`bash` assumptions too. The Factory must run
   in PowerShell.
4. **Dashboard coupled to `python -m http.server` directory listings.** Use a
   real local server with a JSON API (also needed for Tailscale access
   control).
5. **Relying on undocumented transcript formats** without a fallback. If cost
   comes from transcripts, isolate the parser and fail soft (v2 `die`s on an
   unknown model price, `job:273-274`).
6. **Unverifiable prompts.** v2's published reference can't be installed as
   documented because the skill and agents are missing; anything the Factory
   learns from v2 about agent behaviour is second-hand.
7. **Constraints the planners can't see.** Example 003 burned three rounds
   because `protected_paths` wasn't visible to intake/spec. Whatever the
   Factory enforces with hooks should be visible to the skills that plan
   the work, or it will surface as late escalations.
