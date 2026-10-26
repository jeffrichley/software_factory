import { PHASES, type Phase } from "./types";

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
