import {
  specInitials, type FlowRow, type JobData, type MapData, type ReplayData, type ResearchData, type SpecStepData, type TimelineEntry,
  type GraphNodeInput, type NeedsYouCardProps, type StepData, type StepDetailData, type ToSpecData, type ToTicketsData, type WayfinderData,
} from "../ds";

/** Fake data for the gallery only. */

const base = { machine: "mac-studio", repo: "software_factory" };

export const flowRows: FlowRow[] = [
  {
    repo: "software_factory",
    chips: [
      { ...base, id: "glide", label: "Glide demo", name: "#30 Phases and the flow strip", state: "Working", phase: "Green" },
      { ...base, id: "f1", label: "Tracer bullet", name: "#19 Tracer bullet", state: "Needs you", phase: "Red", group: specInitials("The Factory"), groupName: "Spec Job · The Factory" },
      { ...base, id: "f2", label: "Design system", name: "#20 Design system", state: "Working", phase: "Refactor", group: specInitials("The Factory"), groupName: "Spec Job · The Factory" },
      { ...base, id: "f3", label: "Install for real", name: "#21 Install, uninstall and status", state: "Working", phase: "Exploring", group: specInitials("The Factory"), groupName: "Spec Job · The Factory", blocked: true },
      { ...base, id: "f4", label: "Sounds", name: "#24 Needs you and Done sounds", state: "Done", phase: "Merged", machine: "wsl-desk" },
      { ...base, id: "f5", label: "Machine pills", name: "#22 Server down, Stale sessions", state: "Done", seen: true, phase: "Merged" },
      { ...base, id: "f6", label: "Cleanup", name: "#36 Worktree cleanup command", state: "Working", phase: null },
      { ...base, id: "f7", label: "Wayfinder", name: "Software Factory: chart the way", state: "Needs you", phase: "planning", planIcon: "flag", groupName: "Wayfinder" },
    ],
  },
  {
    repo: "gateway",
    chips: [
      { ...base, repo: "gateway", id: "g1", label: "Buyer interviews", name: "#7 Buyer validation interviews", state: "Stale", staleReason: "Machine silent", phase: "Reviewing", machine: "mbp-travel" },
      { ...base, repo: "gateway", id: "g2", label: "research", name: "research session", state: "Done", phase: "planning", planIcon: "search", groupName: "research" },
      { ...base, repo: "gateway", id: "g3", label: "ad hoc", name: "ad hoc session", state: "Working", phase: "planning", planIcon: "terminal", groupName: "ad hoc" },
      // A crowded cell: wraps to two lines, then clips.
      ...Array.from({ length: 9 }, (_, i) => ({
        ...base, repo: "gateway", id: `crowd-${i}`, label: `Ticket number ${i + 1} with a long name`, name: `#${50 + i} Ticket with a long name`,
        state: i % 3 === 0 ? ("Needs you" as const) : ("Working" as const), phase: "Committed" as const, group: specInitials("Gateway"), groupName: "Spec Job · Gateway",
      })),
    ],
  },
];

const m = 60_000;

export const needsCards: Omit<NeedsYouCardProps, "onCopy" | "onOpen" | "selected">[] = [
  { reason: { kind: "permission", tool: "Bash", command: "git push -u origin ticket-20-dashboard-design-system" }, waitingMs: 38_000, repo: "software_factory", kind: "Ticket Job", workItem: { name: "#20 Dashboard design system", url: "#" }, machine: "wsl-desk", session: "sf-ticket-20", terminal: "Windows Terminal · tab 3", resumeCommand: "claude --resume sf-ticket-20" },
  { reason: { kind: "question", text: "Should the flow strip keep a row for repos with no live sessions?" }, waitingMs: 4 * m, repo: "software_factory", kind: "Spec Job", workItem: { name: "#18 Spec: the Factory", url: "#" }, machine: "mac-studio", session: "sf-spec-18", terminal: "iTerm2 · window 1", resumeCommand: "claude --resume sf-spec-18" },
  { reason: { kind: "hitl", ticket: "#14 Choose the cross-platform runtime", questions: ["❓ Q1 - Runtime: Python via uv or Node?", "❓ Q2 - Hook: stdlib only?"] }, waitingMs: 12 * m, repo: "software_factory", kind: "Wayfinder", workItem: { name: "#1 Software Factory: chart the way", url: "#" }, machine: "mac-studio", session: "sf-wayfinder", terminal: "iTerm2 · window 2", resumeCommand: "claude --resume sf-wayfinder" },
  { reason: { kind: "escalation", reason: "CI needs a secret I can't set: GH_TOKEN for the macOS runner." }, waitingMs: 21 * m, repo: "gateway", kind: "Ticket Job", workItem: { name: "#9 Release pipeline", url: "#" }, machine: "win-ps", session: "gw-ticket-9", terminal: null, resumeCommand: "claude --resume gw-ticket-9" },
  { reason: { kind: "error", type: "overloaded_error" }, waitingMs: 2 * 3_600_000 + 5 * m, repo: "gateway", kind: "ad hoc", workItem: null, machine: "wsl-desk", session: "gw-adhoc", terminal: "Windows Terminal · tab 1", resumeCommand: "claude --resume gw-adhoc" },
  { reason: { kind: "no-pr" }, waitingMs: 9 * m, repo: "software_factory", kind: "Ticket Job", workItem: { name: "#36 Worktree cleanup command", url: "#" }, machine: "mac-studio", session: "sf-ticket-36", terminal: "iTerm2 · window 3", resumeCommand: "claude --resume sf-ticket-36" },
];

export const specItems: GraphNodeInput[] = [
  { id: "tracer", deps: [], resolved: true, body: { kind: "step", ticket: "#19 Tracer bullet", phase: "Merged" } },
  { id: "ds", deps: [], resolved: false, body: { kind: "step", ticket: "#20 Dashboard design system", phase: "Refactor", phaseForMs: 6 * m } },
  { id: "install", deps: ["tracer"], resolved: false, body: { kind: "step", ticket: "#21 Install, uninstall and status", phase: "Red", phaseForMs: 3 * m } },
  { id: "api", deps: ["tracer", "ds"], resolved: false, blockedBy: "ds", body: { kind: "step", ticket: "#22 Server down, Stale sessions", phase: "Exploring", phaseForMs: 11 * m } },
  { id: "pills", deps: ["api"], resolved: false, body: { kind: "step", ticket: "#25 Hide/show and Machine filter", phase: null } },
];

export const mapItems: GraphNodeInput[] = [
  { id: "d7", deps: [], resolved: true, muted: true, body: { kind: "decision", name: "Choose where the dashboard gets its information", type: "grilling", mode: "HITL", status: { state: "closed", gist: "hooks → Factory server" } } },
  { id: "d9", deps: ["d7"], resolved: false, claimed: true, body: { kind: "decision", name: "Choose how Needs you and Done are detected", type: "grilling", mode: "HITL", status: { state: "claimed", by: "sf-wayfinder (this session)" }, needs: true } },
  { id: "d10", deps: ["d7"], resolved: false, body: { kind: "decision", name: "Prototype the dashboard", type: "prototype", mode: "HITL/AFK", status: { state: "open" } } },
  { id: "d17", deps: ["d9"], resolved: false, blockedBy: "d9", body: { kind: "decision", name: "Prove the dashboard's shaky fields can be sourced", type: "research", mode: "AFK", status: { state: "open" }, blockedByName: "Choose how Needs you and Done…" } },
];
export const mapFog = ["How Jobs are replayed", "Cleanup of old worktrees"];

export const ticketItems: GraphNodeInput[] = [
  { id: "t1", deps: [], resolved: false, body: { kind: "ticket", name: "#19 Tracer bullet" } },
  { id: "t2", deps: ["t1"], resolved: false, body: { kind: "ticket", name: "#21 Install for real" } },
  { id: "t3", deps: ["t1"], resolved: false, body: { kind: "ticket", name: "#22 Server down, Stale" } },
  { id: "t4", deps: ["t2", "t3"], resolved: false, body: { kind: "ticket", name: "#25 Machine filter" } },
];

const at = (minutesAgo: number) => new Date(Date.now() - minutesAgo * m).toISOString();

export const adhocActions: TimelineEntry[] = [
  { at: at(9), text: "reading src/render/chunk.ts" },
  { at: at(8), text: "searching for \"seamOffset\"" },
  { at: at(6), text: "reading src/render/tileAtlas.ts" },
  { at: at(5), text: "running skill `diagnosing-bugs`" },
  { at: at(3), text: "editing src/render/chunk.ts" },
  { at: at(2), text: "running cargo test" },
  { at: at(1), text: "reading a/very/long/path/that/wraps/in/the/timeline/rather/than/overflowing/its/panel/at/narrow/widths.rs" },
  { at: at(0), text: "reading src/render/chunk.ts" },
];

/** A Ticket Job's Step, struggling in Red, with every part of its detail known. */
export const ticketStep: { step: StepData; detail: StepDetailData } = {
  step: { number: 31, title: "Ticket Job Step detail", phase: "Red", phaseSince: at(23) },
  detail: {
    phaseEvents: [
      { at: at(40), from: null, to: "Exploring" },
      { at: at(30), from: "Exploring", to: "Red" },
      { at: at(26), from: "Red", to: "Green" },
      { at: at(23), from: "Green", to: "Red" },
    ],
    tests: {
      last: "fail", passed: 31, failed: 2,
      runs: ["pass", "fail", "fail", "fail", "fail"].map((result, i) => ({ at: at(20 - i), result: result as "pass" | "fail", passed: 31, failed: result === "fail" ? 2 : 0 })),
    },
    files: [
      { path: "server/factory_server/step_detail.py", edits: 7, added: 96, deleted: 21 },
      { path: "tests/server/test_step_detail.py", edits: 3, added: 62, deleted: 0 },
      { path: "docs/notes.ipynb", edits: 1, added: null, deleted: null },
    ],
    commits: [
      { sha: "77d3a90", message: "Step detail: Phase track and test pulse", files: 4, added: 158, deleted: 12 },
      { sha: "1a7c0f2", message: "Fix review findings", files: 2, added: 14, deleted: 9 },
    ],
    pr: {
      number: 52, url: "https://github.com/jeff/widgets/pull/52", draft: false,
      checks: [{ name: "lint", status: "pass" }, { name: "pytest (ubuntu)", status: "fail" }, { name: "pytest (macos)", status: "pending" }, { name: "docs", status: "skipped" }],
    },
    review: { standards: 2, spec: 1, source: "report" },
    checklist: [
      { text: "Failing test: phase track", status: "completed" },
      { text: "Make the tests pulse", status: "in_progress" },
      { text: "Commits with diffstat", status: "pending" },
    ],
    struggle: { failures: 4, churn: ["server/factory_server/step_detail.py"], silentForS: null },
  },
};

/** A Step just started: nothing known yet, and no todo tools. */
export const freshStep: { step: StepData; detail: StepDetailData } = {
  step: { number: 33, title: null, phase: null, phaseSince: at(1) },
  detail: { phaseEvents: [], tests: null, files: [], commits: [], pr: null, review: null, checklist: null, struggle: { failures: null, churn: [], silentForS: 720 } },
};

/** A merged Ticket Job and its timeline, for the replay. */
export const REPLAY_JOB: JobData = {
  id: "21", sessionId: "7", machine: "wsl", kind: "Ticket Job", repo: "jeff/widgets", startedAt: "2026-10-26T15:30:00Z",
  endedAt: "2026-10-26T16:42:00Z", duplicateOf: null, number: 29, workItem: { name: "Job edges, abandonment and the History list", url: "https://github.com/jeff/widgets/issues/29" },
  stage: "Merged", branch: "ticket-29-job-edges", worktree: null, pr: { number: 48, url: "https://github.com/jeff/widgets/pull/48", draft: false },
};

const rev = (t: number, kind: string, text: string, phase: string | null = null) => ({
  t, at: "", kind, text, step_id: phase ? "9" : null, phase,
});

export const REPLAY: ReplayData = {
  job_id: "21",
  started_at: "2026-10-26T15:30:00Z",
  ended_at: "2026-10-26T15:42:00Z",
  steps: [{ id: "9", number: 29, title: "Job edges, abandonment and the History list", phase: null }],
  events: [
    rev(0, "start", "Job started: #29"),
    rev(12, "action", "reading server/factory_server/store.py"),
    rev(40, "phase", "#29 Exploring", "Exploring"),
    rev(95, "phase", "#29 Red", "Red"),
    rev(130, "test_fail", "Tests fail: uv run pytest tests/server -q"),
    rev(170, "needs", "Needs you: permission for Bash: rm -rf .venv"),
    rev(230, "test_pass", "Tests pass: uv run pytest tests/server -q"),
    rev(231, "phase", "#29 Green", "Green"),
    rev(400, "review", "Review: code-review"),
    rev(401, "phase", "#29 Reviewing", "Reviewing"),
    rev(520, "commit", 'Commit: git commit -am "Job edges"'),
    rev(521, "phase", "#29 Committed", "Committed"),
    rev(600, "pr", "PR: https://github.com/jeff/widgets/pull/48"),
    rev(720, "phase", "#29 Merged", "Merged"),
    rev(720, "end", "Merged"),
  ],
};

/** A Spec Job part-way through: Tickets merged, one in Red, one blocked, one not started. */
export const SPEC_JOB: JobData = {
  id: "30", sessionId: "9", machine: "wsl-desk", kind: "Spec Job", repo: "jeff/widgets", startedAt: at(90), endedAt: null, duplicateOf: null,
  number: 18, workItem: { name: "#18 The Factory", url: "https://github.com/jeff/widgets/issues/18" }, stage: "In progress",
  branch: "worktree-spec-18-the-factory", worktree: "/home/jeff/widgets/.claude/worktrees/spec-18-the-factory",
  pr: { number: 60, url: "https://github.com/jeff/widgets/pull/60", draft: true },
  prTrack: [{ stage: "Draft", at: at(40) }],
  prChecks: [{ name: "lint", status: "pass" }, { name: "unit", status: "pass" }, { name: "integration", status: "pending" }],
};
export const specSteps: SpecStepData[] = [
  { id: "s24", number: 24, title: "Tracer bullet", phase: "Merged", phaseSince: at(70), blockedBy: [] },
  { id: "s25", number: 25, title: "Install and status", phase: "Merged", phaseSince: at(50), blockedBy: [24] },
  { id: "s28", number: 28, title: "Ticket Job: launch to Done", phase: "Red", phaseSince: at(9), blockedBy: [24] },
  { id: "s30", number: 30, title: "Phases and the flow strip", phase: null, phaseSince: at(2), blockedBy: [25] },
  { id: "s31", number: 31, title: "Step detail", phase: "Pending", phaseSince: at(90), blockedBy: [28, 30] },
];
const merged = (sha: string | null, minutesAgo: number): StepDetailData => ({
  ...freshStep.detail, struggle: null, merge: { sha, at: at(minutesAgo) },
});
export const specDetails: Record<string, StepDetailData> = {
  s24: merged("a41c9e2", 70), s25: merged(null, 50), s28: { ...ticketStep.detail, pr: null, review: null },
};

/** A Map with Decision tickets closed, claimed by this session, and open. */
export const MAP: MapData = {
  repo: "jeff/widgets", number: 1, title: "Widget export", url: "https://github.com/jeff/widgets/issues/1",
  destination: "A spec for exporting widgets to CSV and JSON.", fog: ["How exports are scheduled", "Retention of old exports"],
  tickets: [
    { number: 2, title: "Pick the export format", url: "#", state: "closed", type: "research", mode: "AFK", assignees: [], gist: "CSV first, JSON later", blockedBy: [] },
    { number: 3, title: "Choose the columns", url: "#", state: "open", type: "grilling", mode: "HITL", assignees: ["jeffrichley"], gist: null, blockedBy: [2] },
    { number: 4, title: "Prototype the download", url: "#", state: "open", type: "prototype", mode: "HITL", assignees: [], gist: null, blockedBy: [3] },
  ],
};
export const wayfinderPlan: WayfinderData = {
  sessionId: "10", map: 1, ticket: 3, questions: ["Column order", "Include archived widgets?"], created: [4], closed: [2],
};

export const research: ResearchData = {
  sessionId: "11", question: "Can a hook see a test runner's exit code?",
  searches: ["claude code hooks PostToolUseFailure exit code", "PostToolUse Bash tool_response fields"],
  sources: ["https://docs.claude.com/en/docs/claude-code/hooks"],
  findings: { path: "research/hook-exit-codes.md", url: "https://github.com/jeff/widgets/blob/main/research/hook-exit-codes.md" },
};
export const toSpec: ToSpecData = {
  sessionId: "12", map: 1, spec: null,
  outline: ["Problem Statement", "Solution", "User Stories", "Implementation Decisions", "Testing Decisions", "Out of Scope", "Further Notes"]
    .map((section, i) => ({ section, written: i < 3 })),
};
export const toTickets: ToTicketsData = {
  sessionId: "13", spec: 18,
  tickets: [
    { number: 24, title: "Tracer bullet", url: "#", state: "open", blockedBy: [] },
    { number: 25, title: "Install and status", url: "#", state: "open", blockedBy: [24] },
    { number: 26, title: null, url: "#", state: "open", blockedBy: [24] },
  ],
};
