import type { IconName } from "./components/Icon";
import { currentJob } from "./jobs";
import { PENDING, PHASES, SPEC_JOB, type Phase, type SessionState, type StepPhase } from "./types";

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
  /** ms a Working session has had no events; none unless it is quiet. */
  quietMs?: number;
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
  /** null = Phase unknown; Pending = a Spec Job's Step not started yet. */
  phase: StepPhase;
}

/** A flow-strip chip before the dashboard wires it up: the session it opens, and how it looks. */
export interface FlowChipData {
  id: string;
  sessionId: string;
  /** The Step a Step chip shows, opened with its session; none on a session's own chip. */
  stepId?: string;
  label: string;
  name: string;
  state: SessionState;
  seen: boolean;
  phase: Phase | null | "planning";
  planIcon?: IconName;
  /** A Spec Job's Step chip: the Spec's initials, and the Spec named in full for the tooltip. */
  group?: string;
  groupName?: string;
  machine: string;
  repo: string;
  staleReason?: string;
  quietMs?: number;
}

/** A Job as the flow strip needs it; its kind and Work item mark a Spec Job's Step chips with the Spec. */
export interface FlowJob {
  id: string;
  sessionId: string;
  kind?: string;
  number?: number | null;
  workItem?: { name: string } | null;
}

/** A Spec Job's Spec on its Step chips: initials (its number until its title is polled), and its name in full. */
function specGroup(job: FlowJob): { group: string; groupName: string } | null {
  if (job.kind !== SPEC_JOB) return null;
  const name = job.workItem?.name;
  if (name) return { group: specInitials(name), groupName: `${SPEC_JOB} · ${name}` };
  return job.number ? { group: `#${job.number}`, groupName: `${SPEC_JOB} · #${job.number}` } : null;
}

/** Each planning kind's icon on its chip; any other kind (ad hoc) shows a terminal. */
const PLAN_ICONS: Record<string, IconName> = { Wayfinder: "flag", research: "search", "to-spec": "arrow", "to-tickets": "arrow" };

/**
 * The flow strip's rows: one per Tracked repo shown, in order. Each session shown puts its current Job's Steps in
 * their Phases, leaving out Pending ones (a Job with no Step under way shows once, Phase unknown); a session with no
 * Job goes in Planning / ad hoc.
 * Chips take their session's state; a Spec Job's Step chips carry its Spec's initials.
 */
export function flowRows(
  repos: string[],
  sessions: FlowSession[],
  jobs: FlowJob[],
  steps: FlowStepData[],
): { repo: string; chips: FlowChipData[] }[] {
  const rows = repos.map((repo) => ({ repo, chips: [] as FlowChipData[] }));
  for (const s of sessions) {
    const row = rows.find((r) => r.repo === s.repo);
    if (!row) continue;
    const look = {
      sessionId: s.id, state: s.state, seen: s.seen, machine: s.machine, repo: s.repo,
      ...(s.staleReason ? { staleReason: s.staleReason } : {}),
      ...(s.quietMs !== undefined ? { quietMs: s.quietMs } : {}),
    };
    const job = currentJob(jobs, s.id);
    if (!job) {
      row.chips.push({ id: `session-${s.id}`, label: s.kind, name: `${s.kind} session`, phase: "planning", planIcon: PLAN_ICONS[s.kind] ?? "terminal", ...look });
      continue;
    }
    const mine = steps.filter((st) => st.jobId === job.id);
    const group = specGroup(job);
    let shown = 0;
    for (const st of mine) {
      if (st.phase === PENDING) continue;
      const ticket = st.number === null ? "Ticket unknown" : `#${st.number}`;
      row.chips.push({
        id: `step-${st.id}`, stepId: st.id, label: st.title ?? ticket, name: st.title ? `${ticket} ${st.title}` : ticket, phase: st.phase, ...group, ...look,
      });
      shown++;
    }
    if (!shown) row.chips.push({ id: `session-${s.id}`, label: s.kind, name: `${s.kind} session`, phase: null, ...look });
  }
  return rows;
}
