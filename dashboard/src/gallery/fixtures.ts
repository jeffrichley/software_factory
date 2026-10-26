import { specInitials, type FlowRow, type TimelineEntry, type GraphNodeInput, type NeedsYouCardProps } from "../ds";

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
