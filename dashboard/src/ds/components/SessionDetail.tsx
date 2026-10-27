import type { ReactNode } from "react";
import { formatClock, formatDuration } from "../format";
import type { JobData } from "../jobs";
import { AD_HOC, type SessionState } from "../types";
import { Icon } from "./Icon";
import { WorkItemLink } from "./InboxCards";
import { Tag } from "./Tag";
import { Unknown } from "./Unknown";
import { NowLine } from "./NowLine";
import { Eyebrow, Panel } from "./Panel";
import { SkillNote } from "./SessionTable";
import { StateBadge } from "./StateBadge";

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
  inStateMs: number;
  now: string | null;
  /** The detail's title: the Work item, or what kind of session it is. */
  title: ReactNode;
}

/** The top of every session detail view: where it is, what it is, its state and headline. */
export function SessionHeader(p: SessionHeaderProps) {
  return (
    <>
      <nav className="crumbs" aria-label="Zoom level">
        <span>Overview</span><span aria-hidden="true">›</span>
        <span className="mono">{p.machine}</span><span aria-hidden="true">›</span>
        <span>{p.repo}</span><span aria-hidden="true">›</span>
        <span className="cur">{p.kind} session</span>
      </nav>
      <header className="sd-h">
        <Eyebrow>{p.kind}</Eyebrow>
        <h2>{p.title}</h2>
        <div className="sd-meta">
          <StateBadge state={p.state} seen={p.seen} staleReason={p.staleReason} />
          <span>in state {formatDuration(p.inStateMs)}</span>
          <span className="sd-where"><Icon name="terminal" /><span className="mono">{p.machine}</span></span>
          <span>repo <span className="mono">{p.repo}</span></span>
        </div>
        <NowLine now={p.now} />
      </header>
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
}

/** A Ticket Job: its Ticket, where it works, its stage and PR, then the last actions. */
export function TicketJobView({ job, actions, ...header }: TicketJobViewProps) {
  const ticket = job?.workItem ? <WorkItemLink item={job.workItem} /> : job?.number ? `#${job.number}` : <Unknown />;
  return (
    <Detail label="Ticket Job detail">
      <SessionHeader {...header} title={ticket} />
      <Panel title="Job">
        <Facts
          items={[
            ["Ticket", job?.number ? <span className="mono">#{job.number}</span> : <Unknown />],
            ["Stage", job ? <Tag>{job.stage}</Tag> : <Unknown />],
            ["Branch", job?.branch ? <span className="mono">{job.branch}</span> : <Unknown />],
            ["Worktree", job?.worktree ? <span className="mono">{job.worktree}</span> : <Unknown />],
            ["PR", <PrLink pr={job?.pr ?? null} />],
          ]}
        />
      </Panel>
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
