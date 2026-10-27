import type { ReactNode } from "react";
import { formatClock, formatDuration } from "../format";
import { AD_HOC, type SessionState } from "../types";
import { Icon } from "./Icon";
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
          <StateBadge state={p.state} seen={p.seen} />
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
