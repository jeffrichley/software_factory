import type { ReactNode } from "react";
import { formatClock, formatDuration } from "../format";
import type { SessionState } from "../types";
import { Icon } from "./Icon";
import { NowLine } from "./InboxCards";
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
  inStateMs: number;
  now: string | null;
  /** The detail's title: the Work item, or what an ad hoc session is. */
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
        <span className="eyebrow">{p.kind}</span>
        <h2>{p.title}</h2>
        <div className="sd-meta">
          <StateBadge state={p.state} />
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
