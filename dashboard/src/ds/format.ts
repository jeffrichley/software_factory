import type { Phase, SessionState, Tone } from "./types";

/** Time in state, as variant E shows it: 42s · 7m · 2h 14m. */
export function formatDuration(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

export interface StateLook {
  tone: Tone;
  label: string;
}

/** A state's tone and label; a Stale label says why, e.g. "Stale · Machine silent". */
export function stateLook(state: SessionState, seen = false, staleReason?: string): StateLook {
  switch (state) {
    case "Needs you":
      return { tone: "needs", label: state };
    case "Working":
      return { tone: "working", label: state };
    case "Stale":
      return { tone: "stale", label: staleReason ? `${state} · ${staleReason}` : state };
    case "Done":
      return seen ? { tone: "done-seen", label: "Done" } : { tone: "done", label: "Done · unseen" };
  }
}

/** CSS class for a Step's Phase (null = unknown) or a planning / ad hoc session. */
export function phaseClass(phase: Phase | null | "planning"): string {
  if (phase === "planning") return "fplan";
  return phase ? `ph-${phase.toLowerCase()}` : "ph-unknown";
}
