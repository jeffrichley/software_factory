import type { ReactNode } from "react";
import { formatClock, formatDuration } from "../format";
import { isEnded, type JobData } from "../jobs";
import { AD_HOC, type SessionState } from "../types";
import { Icon } from "./Icon";
import { NeedsDetail, WorkItemLink, type NeedsDetailProps } from "./InboxCards";
import { RepoName } from "./RepoName";
import { Tag } from "./Tag";
import { StaleNote, Unknown } from "./Unknown";
import { NowLine } from "./NowLine";
import { Eyebrow, Panel } from "./Panel";
import { StateBadge } from "./StateBadge";
import { StepDetail, type StepData } from "./StepDetail";
import type { StepDetailData } from "../stepDetail";

/** A Tracked session as every view reads it. */
export interface SessionData {
  id: string;
  machine: string;
  repo: string;
  state: SessionState;
  /** Why a Stale session can't be trusted, e.g. "Machine silent". */
  staleReason?: string;
  /** ms a Working session has had no events of its own; none unless it is quiet ("Working · quiet 23m"). */
  quietMs?: number;
  /** Ticket Job, Spec Job, a planning kind (Wayfinder, to-spec, to-tickets, research) or ad hoc. */
  kind: string;
  /** The latest skill the skill table doesn't know, if any; an ad hoc session names it. */
  unknownSkill: string | null;
  /** The "now: …" headline; null until the session does something. */
  now: string | null;
  /** What the headline leaves out, e.g. the full command; shown on hover. */
  nowDetail?: string | null;
  /** Done has been seen by the human. */
  seen?: boolean;
  /** ms the session has been in its state. */
  inStateMs: number;
}

/** "running skill `<name>`": how an ad hoc session names a skill the Factory doesn't know. */
export function SkillNote({ skill }: { skill: string }) {
  return <span className="tsub">running skill <code className="mono">{skill}</code></span>;
}

export interface TimelineEntry {
  /** ISO time of the action. */
  at: string;
  text: string;
}

/** A session's recent actions, oldest first; the latest is marked. */
export function Timeline({ actions }: { actions: TimelineEntry[] }) {
  return (
    <ol className="tl">
      {actions.map((a, i) => (
        <li key={`${a.at}-${i}`}>
          <time dateTime={a.at}>{formatClock(a.at)}</time>
          <span className="tl-m" aria-hidden="true" />
          <span>{a.text}</span>
        </li>
      ))}
    </ol>
  );
}

export interface SessionHeaderProps {
  machine: string;
  repo: string;
  kind: string;
  state: SessionState;
  /** Done only: has the human seen it. */
  seen?: boolean;
  /** Stale only: why its state can't be trusted, e.g. "Machine silent". */
  staleReason?: string;
  /** Working only: ms without events of its own, shown as "Working · quiet 23m". */
  quietMs?: number;
  inStateMs: number;
  now: string | null;
  nowDetail?: string | null;
  /** The detail's title: the Work item, or what kind of session it is. */
  title: ReactNode;
  /** Stale on a silent Machine: ms since the Machine was last seen. */
  machineSilentForMs?: number;
  /** Needs you only: what the centre's Needs you block shows; a view that puts the block elsewhere leaves it out. */
  needs?: Omit<NeedsDetailProps, "waitingMs" | "machine">;
  /** Buttons for the session itself (Hide / Show), beside the zoom crumbs. */
  controls?: ReactNode;
}

/**
 * The top of every session detail view: where it is, what it is, its state and headline; then, on a Stale session,
 * why it can't be trusted and, on a waiting one, the Needs you block (`NeedsDetail`).
 */
export function SessionHeader(p: SessionHeaderProps) {
  return (
    <>
      <div className="sd-top">
        <nav className="crumbs" aria-label="Zoom level">
          <span>Overview</span><span aria-hidden="true">›</span>
          <span className="mono">{p.machine}</span><span aria-hidden="true">›</span>
          <RepoName repo={p.repo} /><span aria-hidden="true">›</span>
          <span className="cur">{p.kind} session</span>
        </nav>
        {p.controls ? <div className="toolbar">{p.controls}</div> : null}
      </div>
      <header className="sd-h">
        <Eyebrow>{p.kind}</Eyebrow>
        <h2>{p.title}</h2>
        <div className="sd-meta">
          <StateBadge state={p.state} seen={p.seen} staleReason={p.staleReason} quietMs={p.quietMs} />
          <span>in state {formatDuration(p.inStateMs)}</span>
          <span className="sd-where"><Icon name="terminal" /><span className="mono">{p.machine}</span></span>
          <span>repo <RepoName className="mono" repo={p.repo} /></span>
        </div>
        <NowLine now={p.now} detail={p.nowDetail} />
      </header>
      {p.state === "Stale" ? <StaleNote reason={p.staleReason ?? "state can't be trusted"} machine={p.machineSilentForMs !== undefined ? p.machine : undefined} silentForMs={p.machineSilentForMs} /> : null}
      {p.needs ? <NeedsDetail {...p.needs} waitingMs={p.inStateMs} machine={p.machine} /> : null}
    </>
  );
}

/** A detail view's body: header, panels and hints stacked. */
export function Detail({ children, label }: { children: ReactNode; label?: string }) {
  return <section className="detail" aria-label={label}>{children}</section>;
}

/** Quiet explanatory text under a panel. */
export function Hint({ children }: { children: ReactNode }) {
  return <p className="hint">{children}</p>;
}

/** Name/value facts about a Job, such as its Ticket, stage, branch and PR. */
export function Facts({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="facts">
      {items.map(([name, value]) => (
        <div key={name}><dt>{name}</dt><dd>{value}</dd></div>
      ))}
    </dl>
  );
}

/** A Job's PR as a link; a draft is marked as one. */
export function PrLink({ pr }: { pr: JobData["pr"] }) {
  if (!pr) return <Unknown />;
  return (
    <>
      <a className="wi mono" href={pr.url}>{pr.number ? `#${pr.number}` : pr.url}</a>
      {pr.draft ? <> <Tag tone="unknown">draft</Tag></> : null}
    </>
  );
}

export interface TicketJobViewProps extends Omit<SessionHeaderProps, "title"> {
  /** The session's current Job; null until one starts. */
  job: JobData | null;
  actions: TimelineEntry[];
  /** The Job's one Step, with what it has done; absent until the Job starts. */
  step?: { step: StepData; detail: StepDetailData | null } | null;
  /** The time now (ms), for time in Phase. */
  nowMs?: number;
  /** Marks the Job abandoned; offered only while the Job is active. */
  onAbandon?: () => void;
}

/** A Ticket Job: its Ticket, where it works, its stage and PR, its Step's detail, then the last actions. */
export function TicketJobView({ job, actions, step, nowMs = Date.now(), onAbandon, ...header }: TicketJobViewProps) {
  const ticket = job?.workItem ? <WorkItemLink item={job.workItem} /> : job?.number ? `#${job.number}` : <Unknown />;
  return (
    <Detail label="Ticket Job detail">
      <SessionHeader {...header} title={ticket} />
      <Panel title="Job">
        <Facts
          items={[
            ["Ticket", job?.number ? <span className="mono">#{job.number}</span> : <Unknown />],
            ["Stage", job ? (
              <>
                <Tag>{job.stage}</Tag>
                {job.duplicateOf ? <> <Tag tone="struggle">duplicate of Job {job.duplicateOf}</Tag></> : null}
              </>
            ) : <Unknown />],
            ["Branch", job?.branch ? <span className="mono">{job.branch}</span> : <Unknown />],
            ["Worktree", job?.worktree ? <span className="mono">{job.worktree}</span> : <Unknown />],
            ["PR", <PrLink pr={job?.pr ?? null} />],
          ]}
        />
        {job && onAbandon && !isEnded(job.stage) ? (
          <div className="toolbar">
            <button type="button" className="btn" onClick={onAbandon}>Mark abandoned</button>
          </div>
        ) : null}
      </Panel>
      {step ? <StepDetail step={step.step} detail={step.detail} nowMs={nowMs} /> : null}
      <Panel title={actions.length ? `Last ${actions.length} actions` : "Last actions"}>
        {actions.length ? <Timeline actions={actions} /> : <Hint>No actions yet.</Hint>}
      </Panel>
    </Detail>
  );
}

export interface AdHocViewProps extends Omit<SessionHeaderProps, "title"> {
  /** The latest skill the skill table doesn't know, if any. */
  unknownSkill: string | null;
  actions: TimelineEntry[];
}

/**
 * State, headline and the last actions: the whole detail of an ad hoc session, which has no Job, Step or Phase.
 * Other kinds show it too, titled by their kind, until their own view arrives.
 */
export function AdHocView({ actions, unknownSkill, ...header }: AdHocViewProps) {
  const adHoc = header.kind === AD_HOC;
  const title = adHoc
    ? <>Ad hoc session{unknownSkill ? <SkillNote skill={unknownSkill} /> : null}</>
    : `${header.kind} session`;
  return (
    <Detail label={`${header.kind} session detail`}>
      <SessionHeader {...header} title={title} />
      <Panel title={actions.length ? `Last ${actions.length} actions` : "Last actions"}>
        {actions.length ? <Timeline actions={actions} /> : <Hint>No actions yet.</Hint>}
      </Panel>
      <Hint>
        {adHoc
          ? "Ad hoc sessions run no skill the Factory knows, so there is no Job, Step or Phase."
          : `The ${header.kind} view is not built yet; this shows the session’s state, headline and last actions.`}
      </Hint>
    </Detail>
  );
}
