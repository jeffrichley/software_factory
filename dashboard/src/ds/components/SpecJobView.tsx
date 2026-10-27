import { useMemo, useState } from "react";
import { isEnded, type JobData } from "../jobs";
import { specGraph, ticketName, type SpecStepData } from "../specDag";
import { GraphView } from "./Graph";
import { WorkItemLink } from "./InboxCards";
import { Panel } from "./Panel";
import { mergesOf, prTrack } from "../specJob";
import { Icon } from "./Icon";
import { Merges, PrTrack, Stat, StatTiles } from "./SpecProgress";
import { Checks, Review, StepDetail } from "./StepDetail";
import type { StepDetailData } from "../stepDetail";
import { Detail, Hint, SessionHeader, Timeline, type SessionHeaderProps, type TimelineEntry } from "./SessionDetail";
import { Tag } from "./Tag";
import { Unknown } from "./Unknown";

export interface SpecJobViewProps extends Omit<SessionHeaderProps, "title"> {
  /** The session's current Job; null until one starts. */
  job: JobData | null;
  /** The Job's Steps, one per Ticket of its Spec. */
  steps: SpecStepData[];
  /** What each Step has done, by Step id. */
  details?: Record<string, StepDetailData>;
  /** Code-review's findings on the whole integration branch, when known. */
  review?: StepDetailData["review"];
  /** The time now (ms), for time in Phase. */
  nowMs: number;
  actions: TimelineEntry[];
  /** Marks the Job abandoned; offered only while the Job is active. */
  onAbandon?: () => void;
  /** The Step whose detail is open, when the dashboard chooses it (e.g. its flow-strip chip was clicked). */
  stepId?: string;
  /** A Step picked in the Ticket DAG; without it the view keeps the choice itself. */
  onSelectStep?: (stepId: string) => void;
}

/** A Spec Job as variant E: stat tiles (integration branch, Tickets merged, final code review, Spec PR), its Ticket DAG, the
 * merges into the integration branch, the final review and the PR track, then the Step opened from the DAG. */
export function SpecJobView({
  job, steps, details = {}, review = null, nowMs, actions, onAbandon, stepId: chosen, onSelectStep, ...header
}: SpecJobViewProps) {
  const [own, setOwn] = useState<string>();
  const stepId = chosen ?? own;
  const setStepId = onSelectStep ?? setOwn;
  const items = useMemo(() => specGraph(steps, nowMs), [steps, nowMs]);
  const step = steps.find((s) => s.id === stepId);
  const merged = steps.filter((s) => s.phase === "Merged").length;
  const spec = job?.workItem ? <WorkItemLink item={job.workItem} /> : job?.number ? `#${job.number}` : <Unknown />;
  const branch = job?.branch ?? null;
  const merges = mergesOf(steps, Object.fromEntries(steps.map((s) => [s.id, details[s.id]?.merge])));
  const track = job?.pr ? prTrack(job.pr, job.prTrack) : [];
  const prStage = track.find((s) => s.status === "current")?.stage;
  const allMerged = steps.length > 0 && merged === steps.length;
  const findings = review ? review.standards + review.spec : null;
  return (
    <Detail label="Spec Job detail">
      <SessionHeader {...header} title={spec} />
      <StatTiles>
        <Stat label="Integration branch">{branch ?? <Unknown />}</Stat>
        <Stat label="Merged">{steps.length ? `${merged} / ${steps.length} Tickets` : <Unknown />}</Stat>
        <Stat label="Final code review">
          {findings !== null ? `${findings} ${findings === 1 ? "finding" : "findings"}` : allMerged ? "Not reviewed yet" : "Waiting"}
        </Stat>
        <Stat label="Spec PR">
          {job?.pr ? <a className="wi" href={job.pr.url}>{`${job.pr.number ? `#${job.pr.number}` : "PR"} · ${prStage}`}</a> : "No PR yet"}
        </Stat>
      </StatTiles>
      <div className="job-line">
        {job ? <Tag>{job.stage}</Tag> : null}
        {job?.duplicateOf ? <Tag tone="struggle">duplicate of Job {job.duplicateOf}</Tag> : null}
        <span className="muted">worktree {job?.worktree ? <span className="mono">{job.worktree}</span> : <Unknown />}</span>
        {job && onAbandon && !isEnded(job.stage) ? (
          <button type="button" className="btn" onClick={onAbandon}>Mark abandoned</button>
        ) : null}
      </div>
      <Panel title="Ticket DAG">
        {steps.length ? (
          <GraphView items={items} selectedId={stepId} onSelect={setStepId} label={`Ticket DAG for ${job?.workItem?.name ?? "the Spec"}`} />
        ) : (
          <Hint>No Tickets yet: they appear once the Spec's child Tickets are read from GitHub.</Hint>
        )}
      </Panel>
      <div className="spec-cols">
        <Merges branch={branch} merges={merges} total={steps.length} />
        <Panel title="Final code review">
          {review ? <Review review={review} /> : (
            <Hint>
              {allMerged ? "Not reviewed yet: code-review runs on the whole integration branch now every Ticket is merged."
                : `Starts when ${steps.length || "every"} / ${steps.length || "every"} Tickets are merged into ${branch ?? "the integration branch"}.`}
            </Hint>
          )}
        </Panel>
        <Panel title="Pull request">
          {job?.pr ? (
            <>
              <div className="pr-line">
                <Icon name="pr" />
                <a className="wi" href={job.pr.url}>{job.pr.number ? `PR #${job.pr.number}` : job.pr.url}</a>
                {branch ? <span className="muted">{branch}</span> : null}
              </div>
              <PrTrack stages={track} />
              <Checks checks={job.prChecks} />
            </>
          ) : <Hint>No PR yet: implement-spec opens a draft once Tickets are merged, and marks it ready for review at the end.</Hint>}
        </Panel>
      </div>
      {step ? <StepDetail step={step} detail={details[step.id] ?? null} nowMs={nowMs} inSpecJob blockers={blockersOf(step, steps)} integrationBranch={branch} /> : steps.length ? <Hint>Select a Ticket in the DAG to open its Step.</Hint> : null}
      <Panel title={actions.length ? `Last ${actions.length} actions` : "Last actions"}>
        {actions.length ? <Timeline actions={actions} /> : <Hint>No actions yet.</Hint>}
      </Panel>
    </Detail>
  );
}

/** The Tickets still blocking a Step (not merged yet), by name. */
function blockersOf(step: SpecStepData, steps: SpecStepData[]): string[] {
  return step.blockedBy.flatMap((n) => {
    const s = steps.find((x) => x.number === n);
    return s?.phase === "Merged" ? [] : [s ? ticketName(s) : `#${n}`];
  });
}
