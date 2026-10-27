import type { GraphNodeInput } from "./components/Graph";
import { PENDING, type StepPhase } from "./types";

/** A Spec Job's Step as its Ticket DAG needs it. */
export interface SpecStepData {
  id: string;
  /** The Ticket's number; null until known. */
  number: number | null;
  /** The Ticket's title; null until polled. */
  title: string | null;
  /** Pending until a subagent starts on it; null = Phase unknown. */
  phase: StepPhase;
  phaseSince: string;
  /** The Tickets that block this one (from GitHub's issue dependencies). */
  blockedBy: number[];
}

export function ticketName(s: { number: number | null; title: string | null }): string {
  if (s.number === null) return "Ticket unknown";
  return s.title ? `#${s.number} ${s.title}` : `#${s.number}`;
}

/**
 * A Spec Job's Ticket DAG in the one graph grammar: each Step depends on the Steps of the Tickets that block it.
 * A Merged Step is resolved; a Step already started on a blocker not yet merged is blocked by it, while a Pending
 * one only waits; started Steps are never frontier, so the frontier is what implement-spec can take now.
 */
export function specGraph(steps: SpecStepData[], now: number): GraphNodeInput[] {
  const byNumber = new Map(steps.filter((s) => s.number !== null).map((s) => [s.number, s]));
  return steps.map((s) => {
    const deps = s.blockedBy.flatMap((n) => byNumber.get(n)?.id ?? []);
    const started = s.phase !== PENDING;
    const blocker = started ? deps.find((d) => steps.find((x) => x.id === d)?.phase !== "Merged") : undefined;
    return {
      id: s.id,
      deps,
      resolved: s.phase === "Merged",
      claimed: started,
      ...(blocker ? { blockedBy: blocker } : {}),
      body: { kind: "step", ticket: ticketName(s), phase: s.phase, phaseForMs: now - Date.parse(s.phaseSince) },
    };
  });
}
