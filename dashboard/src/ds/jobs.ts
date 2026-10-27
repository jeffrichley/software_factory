/** The Job stages that end a Job and move it to History. */
export const ENDED_STAGES = ["Merged", "Closed", "Abandoned"] as const;

/** A Job as the dashboard shows it. */
export interface JobData {
  id: string;
  sessionId: string;
  kind: string;
  repo: string;
  /** ISO time the Job started. */
  startedAt: string;
  /** The active Job already on this Work item when it started: flagged, never blocked. */
  duplicateOf: string | null;
  /** The Work item's number; null until the Job reports it. */
  number: number | null;
  /** The Work item's title and link; null until polled (or while the number is unknown). */
  workItem: { name: string; url: string } | null;
  /** In progress, PR open, … */
  stage: string;
  branch: string | null;
  worktree: string | null;
  /** The Job's PR; a draft is shown as a link only. */
  pr: { number: number | null; url: string; draft: boolean } | null;
}

/** Merged, Closed or Abandoned: the Job is over and belongs in History. */
export function isEnded(stage: string): boolean {
  return (ENDED_STAGES as readonly string[]).includes(stage);
}

/** History: the Jobs that have ended, latest started first (ids grow). */
export function historyOf<J extends { id: string; stage: string }>(jobs: J[]): J[] {
  return jobs.filter((j) => isEnded(j.stage)).sort((a, b) => Number(b.id) - Number(a.id));
}

/** A session's current Job: the one started last (ids grow), or null when it has none. */
export function currentJob<J extends { id: string; sessionId: string }>(jobs: J[], sessionId: string): J | null {
  let latest: J | null = null;
  for (const j of jobs) {
    if (j.sessionId === sessionId && (!latest || Number(j.id) > Number(latest.id))) latest = j;
  }
  return latest;
}
