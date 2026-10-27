import type { StepPhase } from "./types";

/**
 * History replay: a finished Job's timeline (GET /api/jobs/{id}/replay), scrubbed through time. Times are seconds
 * since the Job started.
 */

/** What happened at a moment of the Job: start, phase, action, test_pass, test_fail, commit, review, needs, pr, end. */
export interface ReplayEvent {
  t: number;
  at: string;
  kind: string;
  text: string;
  /** A Phase change's Step and Phase; null otherwise. */
  step_id: string | null;
  phase: string | null;
}

export interface ReplayData {
  job_id: string;
  started_at: string;
  /** When the Job was first seen Merged, Closed or Abandoned; null while it hasn't ended. */
  ended_at: string | null;
  /** Each Step with the Phase it was added in: Pending (a Spec Job's Ticket) or null = unknown. */
  steps: { id: string; number: number | null; title: string | null; phase: StepPhase }[];
  events: ReplayEvent[];
}

/** The event kinds marked on the scrubber; actions are listed but too many to mark. */
export const MARKED_KINDS = ["phase", "test_pass", "test_fail", "commit", "review", "needs", "pr", "end"] as const;

/** The replay at time `t`: each Step's Phase then (Pending, or null = unknown), and the index of the last event reached (-1 = none). */
export function replayFrame(replay: ReplayData, t: number): { phases: Record<string, StepPhase>; current: number } {
  const phases: Record<string, StepPhase> = Object.fromEntries(replay.steps.map((s) => [s.id, s.phase]));
  let current = -1;
  replay.events.forEach((e, i) => {
    if (e.t > t) return;
    current = i;
    if (e.kind === "phase" && e.step_id) phases[e.step_id] = e.phase as StepPhase;
  });
  return { phases, current };
}

/** How long the replay runs: to the Job's end, else its last event; at least a second. */
export function replayLength(replay: ReplayData): number {
  const end = replay.ended_at
    ? (Date.parse(replay.ended_at) - Date.parse(replay.started_at)) / 1000
    : Math.max(0, ...replay.events.map((e) => e.t));
  return Math.max(1, Math.round(end));
}

/** Time since the Job started: 1:05, or 1:02:05 past an hour. */
export function formatOffset(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const ss = String(s % 60).padStart(2, "0");
  const m = Math.floor(s / 60);
  return m < 60 ? `${m}:${ss}` : `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}:${ss}`;
}
