/** The Job stages that end a Job and move it to History. */
export const ENDED_STAGES = ["Merged", "Closed", "Abandoned"] as const;

import type { IconName } from "./components/Icon";
import { formatAgo, formatDuration } from "./format";

/** A Job as the dashboard shows it. */
export interface JobData {
  id: string;
  sessionId: string;
  /** The Machine its session runs on. */
  machine: string;
  kind: string;
  repo: string;
  /** ISO time the Job started. */
  startedAt: string;
  /** ISO time the server first saw it Merged, Closed or Abandoned; null before. */
  endedAt: string | null;
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

/** History: the Jobs that have ended, latest started first (ids grow), leaving out those on hidden Machines. */
export function historyOf<J extends { id: string; stage: string; machine?: string }>(jobs: J[], hiddenMachines: string[] = []): J[] {
  return jobs
    .filter((j) => isEnded(j.stage) && !(j.machine !== undefined && hiddenMachines.includes(j.machine)))
    .sort((a, b) => Number(b.id) - Number(a.id));
}

/** A session's current Job: the one started last (ids grow), or null when it has none. */
export function currentJob<J extends { id: string; sessionId: string }>(jobs: J[], sessionId: string): J | null {
  let latest: J | null = null;
  for (const j of jobs) {
    if (j.sessionId === sessionId && (!latest || Number(j.id) > Number(latest.id))) latest = j;
  }
  return latest;
}

/** How each ended stage reads in History, as in variant E. */
const OUTCOMES: Record<string, { outcome: string; icon: IconName; tone: string }> = {
  Merged: { outcome: "PR merged", icon: "check", tone: "merged" },
  Closed: { outcome: "PR closed", icon: "x", tone: "closed" },
  Abandoned: { outcome: "Abandoned", icon: "flag", tone: "abandoned" },
};

/** An ended Job as a History row shows it: its outcome, how long it took and how long ago it ended (null = unknown,
 * until the server has seen it end). */
export function endedJob(job: { stage: string; startedAt: string; endedAt: string | null }, nowMs: number) {
  const ended = job.endedAt ? Date.parse(job.endedAt) : null;
  return {
    ...(OUTCOMES[job.stage] ?? { outcome: job.stage, icon: "clock" as IconName, tone: "closed" }),
    took: ended === null ? null : formatDuration(ended - Date.parse(job.startedAt)),
    ago: ended === null ? null : formatAgo(nowMs - ended),
  };
}
