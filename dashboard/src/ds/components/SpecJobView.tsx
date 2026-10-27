import { useMemo, useState } from "react";
import { formatDuration } from "../format";
import { isEnded, type JobData } from "../jobs";
import { specGraph, ticketName, type SpecStepData } from "../specDag";
import { PENDING } from "../types";
import { GraphView } from "./Graph";
import { WorkItemLink } from "./InboxCards";
import { Panel } from "./Panel";
import { PhaseTrack } from "./PhaseTrack";
import { Detail, Facts, Hint, PrLink, SessionHeader, Timeline, type SessionHeaderProps, type TimelineEntry } from "./SessionDetail";
import { Tag } from "./Tag";
import { Unknown } from "./Unknown";

export interface SpecJobViewProps extends Omit<SessionHeaderProps, "title"> {
  /** The session's current Job; null until one starts. */
  job: JobData | null;
  /** The Job's Steps, one per Ticket of its Spec. */
  steps: SpecStepData[];
  /** The time now (ms), for time in Phase. */
  nowMs: number;
  actions: TimelineEntry[];
  /** Marks the Job abandoned; offered only while the Job is active. */
  onAbandon?: () => void;
}

/** A Spec Job: its Spec, integration branch, stage and PR, its Ticket DAG, and the Step opened from the DAG. */
export function SpecJobView({ job, steps, nowMs, actions, onAbandon, ...header }: SpecJobViewProps) {
  const [stepId, setStepId] = useState<string>();
  const items = useMemo(() => specGraph(steps, nowMs), [steps, nowMs]);
  const step = steps.find((s) => s.id === stepId);
  const merged = steps.filter((s) => s.phase === "Merged").length;
  const spec = job?.workItem ? <WorkItemLink item={job.workItem} /> : job?.number ? `#${job.number}` : <Unknown />;
  return (
    <Detail label="Spec Job detail">
      <SessionHeader {...header} title={spec} />
      <Panel title="Job">
        <Facts
          items={[
            ["Spec", job?.number ? <span className="mono">#{job.number}</span> : <Unknown />],
            ["Stage", job ? (
              <>
                <Tag>{job.stage}</Tag>
                {job.duplicateOf ? <> <Tag tone="struggle">duplicate of Job {job.duplicateOf}</Tag></> : null}
              </>
            ) : <Unknown />],
            ["Integration branch", job?.branch ? <span className="mono">{job.branch}</span> : <Unknown />],
            ["Worktree", job?.worktree ? <span className="mono">{job.worktree}</span> : <Unknown />],
            ["Merged", steps.length ? `${merged} / ${steps.length} Tickets` : <Unknown />],
            ["PR", <PrLink pr={job?.pr ?? null} />],
          ]}
        />
        {job && onAbandon && !isEnded(job.stage) ? (
          <div className="toolbar">
            <button type="button" className="btn" onClick={onAbandon}>Mark abandoned</button>
          </div>
        ) : null}
      </Panel>
      <Panel title="Ticket DAG">
        {steps.length ? (
          <GraphView items={items} selectedId={stepId} onSelect={setStepId} label={`Ticket DAG for ${job?.workItem?.name ?? "the Spec"}`} />
        ) : (
          <Hint>No Tickets yet: they appear once the Spec's child Tickets are read from GitHub.</Hint>
        )}
      </Panel>
      {step ? <StepPanel step={step} steps={steps} nowMs={nowMs} /> : steps.length ? <Hint>Select a Ticket in the DAG to open its Step.</Hint> : null}
      <Panel title={actions.length ? `Last ${actions.length} actions` : "Last actions"}>
        {actions.length ? <Timeline actions={actions} /> : <Hint>No actions yet.</Hint>}
      </Panel>
    </Detail>
  );
}

function StepPanel({ step, steps, nowMs }: { step: SpecStepData; steps: SpecStepData[]; nowMs: number }) {
  const blockers = step.blockedBy.map((n) => {
    const s = steps.find((x) => x.number === n);
    return s ? ticketName(s) : `#${n}`;
  });
  return (
    <Panel title={`Step · ${ticketName(step)}`} label="Step detail">
      <Facts
        items={[
          ["Phase", step.phase === PENDING ? <Tag tone="unknown">Pending</Tag> : <PhaseTrack phase={step.phase} compact />],
          ["In it for", step.phase === null ? <Unknown /> : formatDuration(nowMs - Date.parse(step.phaseSince))],
          ["Blocked by", blockers.length ? blockers.join(", ") : "nothing"],
        ]}
      />
    </Panel>
  );
}
