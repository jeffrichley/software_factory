import type { IconName } from "./components/Icon";
import { currentJob } from "./jobs";
import { PHASES, type Phase, type SessionState } from "./types";

export const FLOW_COLUMNS = ["Phase unknown", ...PHASES, "Planning / ad hoc"] as const;

/** Column index for a Step (null Phase = unknown) or a planning / ad hoc session. */
export function flowColumn(of: { phase: Phase | null } | "planning"): number {
  if (of === "planning") return FLOW_COLUMNS.length - 1;
  return of.phase ? PHASES.indexOf(of.phase) + 1 : 0;
}

export function specInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

/** A live session as the flow strip needs it. */
export interface FlowSession {
  id: string;
  machine: string;
  repo: string;
  state: SessionState;
  seen: boolean;
  staleReason?: string;
  kind: string;
}

/** A Step as the server reports it. */
export interface FlowStepData {
  id: string;
  jobId: string;
  sessionId: string;
  repo: string;
  /** The Ticket's number; null until the Job reports it. */
  number: number | null;
  /** The Ticket's title; null until polled. */
  title: string | null;
  /** null = Phase unknown. */
  phase: Phase | null;
}

/** A flow-strip chip before the dashboard wires it up: the session it opens, and how it looks. */
export interface FlowChipData {
  id: string;
  sessionId: string;
  label: string;
  name: string;
  state: SessionState;
  seen: boolean;
  phase: Phase | null | "planning";
  planIcon?: IconName;
  machine: string;
  repo: string;
  staleReason?: string;
}

/** Each planning kind's icon on its chip; any other kind (ad hoc) shows a terminal. */
const PLAN_ICONS: Record<string, IconName> = { Wayfinder: "flag", research: "search", "to-spec": "arrow", "to-tickets": "arrow" };

/**
 * The flow strip's rows: one per Tracked repo shown, in order. Each session shown puts its current Job's Steps in
 * their Phases (a Job with no Steps yet shows once, Phase unknown); a session with no Job goes in Planning / ad hoc.
 * Chips take their session's state.
 */
export function flowRows(
  repos: string[],
  sessions: FlowSession[],
  jobs: { id: string; sessionId: string }[],
  steps: FlowStepData[],
): { repo: string; chips: FlowChipData[] }[] {
  const rows = repos.map((repo) => ({ repo, chips: [] as FlowChipData[] }));
  for (const s of sessions) {
    const row = rows.find((r) => r.repo === s.repo);
    if (!row) continue;
    const look = {
      sessionId: s.id, state: s.state, seen: s.seen, machine: s.machine, repo: s.repo,
      ...(s.staleReason ? { staleReason: s.staleReason } : {}),
    };
    const job = currentJob(jobs, s.id);
    if (!job) {
      row.chips.push({ id: `session-${s.id}`, label: s.kind, name: `${s.kind} session`, phase: "planning", planIcon: PLAN_ICONS[s.kind] ?? "terminal", ...look });
      continue;
    }
    const mine = steps.filter((st) => st.jobId === job.id);
    if (!mine.length) row.chips.push({ id: `session-${s.id}`, label: s.kind, name: `${s.kind} session`, phase: null, ...look });
    for (const st of mine) {
      const ticket = st.number === null ? "Ticket unknown" : `#${st.number}`;
      row.chips.push({
        id: `step-${st.id}`, label: st.title ?? ticket, name: st.title ? `${ticket} ${st.title}` : ticket, phase: st.phase, ...look,
      });
    }
  }
  return rows;
}
