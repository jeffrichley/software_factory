import { formatDuration } from "./format";

/** One change of a Step's Phase; null = Phase unknown. */
export interface PhaseChangeData {
  at: string;
  from: string | null;
  to: string | null;
}

export interface TestRunData {
  at: string;
  result: "pass" | "fail";
  /** From the runner's summary line; null when it printed none. */
  passed: number | null;
  failed: number | null;
}

/** Why a Step looks stuck: failing runs in a row, files edited over and over without a pass, silence while Working. */
export interface StruggleData {
  failures: number | null;
  churn: string[];
  silentForS: number | null;
}

export interface ChecklistItem {
  text: string;
  /** pending, in_progress or completed. */
  status: string;
}

export interface CheckData {
  name: string;
  status: "pass" | "fail" | "pending" | "skipped";
}

export interface CommitData {
  sha: string;
  message: string;
  files: number;
  added: number;
  deleted: number;
}

/** Code-review's findings per axis: reported by the agent, or read from its summary line. */
export interface ReviewData {
  standards: number;
  spec: number;
  source: "report" | "summary";
}

/** Everything about a Step beyond its Phase, as the server's `step_details` gives it. */
export interface StepDetailData {
  phaseEvents: PhaseChangeData[];
  /** null until a test run. */
  tests: { last: "pass" | "fail"; passed: number | null; failed: number | null; runs: TestRunData[] } | null;
  files: { path: string; edits: number }[];
  commits: CommitData[];
  /** A Ticket Job's PR; checks null until read. A Spec Job's Steps merge into its integration branch instead. */
  pr: { number: number | null; url: string; draft: boolean; checks: CheckData[] | null } | null;
  review: ReviewData | null;
  /** null: the agent has no todo or task tools, so no checklist. */
  checklist: ChecklistItem[] | null;
  struggle: StruggleData | null;
}

/** The struggle badge's tags, one per reason that holds. */
export function struggleLabels(s: StruggleData | null): string[] {
  if (!s) return [];
  return [
    ...(s.failures ? [`Struggling · ${s.failures} test failures`] : []),
    ...(s.churn.length ? [`Churn · ${s.churn.join(", ")}`] : []),
    ...(s.silentForS !== null ? [`Silence · ${formatDuration(s.silentForS * 1000)}`] : []),
  ];
}

/** A commit's diffstat as `n` blocks: added ("a"), deleted ("d"), each shown when it has any lines. */
export function diffBlocks(added: number, deleted: number, n = 5): ("a" | "d" | "")[] {
  const total = added + deleted;
  if (!total) return Array<"">(n).fill("");
  const a = Math.max(added ? 1 : 0, Math.min(n - (deleted ? 1 : 0), Math.round((added / total) * n)));
  return [...Array<"a">(a).fill("a"), ...Array<"d">(n - a).fill("d")];
}

export function phaseChange(e: PhaseChangeData): string {
  return `${e.from ?? "Phase unknown"} → ${e.to ?? "Phase unknown"}`;
}

/** The checklist item being worked: the one in progress, else the first not done; -1 when all are done. */
export function currentItem(items: ChecklistItem[]): number {
  const working = items.findIndex((i) => i.status === "in_progress");
  return working >= 0 ? working : items.findIndex((i) => i.status !== "completed");
}
