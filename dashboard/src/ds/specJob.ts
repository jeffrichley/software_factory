import type { JobData } from "./jobs";
import type { SpecStepData } from "./specDag";

/** Where a PR is: Draft, Ready (for review), Merged, or Closed without merging. */
export type PrStage = "Draft" | "Ready" | "Merged" | "Closed";

/** A stage the Job's PR was seen to reach, and when (from the server's poll). */
export interface PrTrackEntry {
  stage: PrStage;
  at: string;
}

export interface PrTrackStage {
  stage: PrStage;
  /** When the PR reached it; null when not reached, or not seen (a PR first seen ready was never seen a draft). */
  at: string | null;
  status: "done" | "current" | "todo";
}

/**
 * The PR track Draft → Ready → Merged (Closed in Merged's place for a PR closed unmerged): the stage the PR is in now
 * is current, the ones before it done, with when each was reached as far as the poll saw it.
 */
export function prTrack(pr: NonNullable<JobData["pr"]>, track: PrTrackEntry[]): PrTrackStage[] {
  const current: PrStage = track.at(-1)?.stage ?? (pr.draft ? "Draft" : "Ready");
  const stages: PrStage[] = ["Draft", "Ready", current === "Closed" ? "Closed" : "Merged"];
  const at = stages.indexOf(current);
  return stages.map((stage, i) => ({
    stage,
    at: i <= at ? track.filter((t) => t.stage === stage).at(-1)?.at ?? null : null,
    status: i < at ? "done" : i === at ? "current" : "todo",
  }));
}

/** A Spec Job's Step merged into its integration branch: when, and the commit it left the branch on (as git printed it on a
 * fast-forward, else as the hook read HEAD just after the merge; null when neither says). */
export interface MergeData {
  sha: string | null;
  at: string;
}

export interface MergeEntry {
  step: SpecStepData;
  sha: string | null;
  /** null: Merged without its merge seen (e.g. its PR merged). */
  at: string | null;
}

/** The Steps merged into the integration branch, in merge order; a Step Merged without its merge seen comes last. */
export function mergesOf(steps: SpecStepData[], merges: Record<string, MergeData | null | undefined>): MergeEntry[] {
  return steps
    .filter((s) => merges[s.id] || s.phase === "Merged")
    .map((s) => ({ step: s, sha: merges[s.id]?.sha ?? null, at: merges[s.id]?.at ?? null }))
    .sort((a, b) => (a.at === null ? 1 : 0) - (b.at === null ? 1 : 0) || (a.at ?? "").localeCompare(b.at ?? ""));
}
