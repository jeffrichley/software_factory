import type { ReactNode } from "react";
import { formatDuration } from "../format";
import { Icon, type IconName } from "./Icon";
import { NowLine } from "./NowLine";
import { Unknown } from "./Unknown";

export type NeedsReason =
  | { kind: "permission"; tool: string; command: string }
  | { kind: "question"; text: string }
  | { kind: "hitl"; ticket: string; questions?: string[] }
  | { kind: "escalation"; reason: string }
  | { kind: "error"; type: string }
  | { kind: "no-pr" };

const REASON: Record<NeedsReason["kind"], [string, IconName]> = {
  permission: ["Permission prompt", "shield"],
  question: ["Question", "question"],
  hitl: ["HITL ticket", "flag"],
  escalation: ["Escalation", "flag"],
  error: ["Stopped on error", "alert"],
  "no-pr": ["Ended without a PR", "alert"],
};

export interface WorkItemRef {
  name: string;
  url: string;
}

export function WorkItemLink({ item }: { item: WorkItemRef | null }) {
  return item ? <a className="wi" href={item.url}>{item.name}</a> : <Unknown />;
}

/** Title and icon when the reason isn't known: shown as unknown, never guessed. */
const UNKNOWN_REASON: [string, IconName] = ["Needs you", "alert"];

function NeedsBody({ reason }: { reason: NeedsReason | null }): ReactNode {
  if (!reason) return <p className="needs-q"><Unknown /></p>;
  switch (reason.kind) {
    case "permission":
      return (
        <>
          <span className="eyebrow nlabel">{reason.tool} wants to run</span>
          <pre className="cmd">{reason.command}</pre>
        </>
      );
    case "question":
      return <p className="needs-q">{reason.text}</p>;
    case "hitl":
      return (
        <>
          <p className="needs-q">{reason.ticket}</p>
          {reason.questions?.length ? (
            <ul className="needs-qs">{reason.questions.map((q) => <li key={q}>{q}</li>)}</ul>
          ) : null}
        </>
      );
    case "escalation":
      return <p className="needs-q">{reason.reason}</p>;
    case "error":
      return <p className="needs-q">stopped on error: {reason.type}</p>;
    case "no-pr":
      return <p className="needs-q">ended without a PR</p>;
  }
}

export interface NeedsYouCardProps {
  /** Why the session Needs you; null while unknown. */
  reason: NeedsReason | null;
  waitingMs: number;
  repo: string;
  /** Session kind; null while unknown. */
  kind: string | null;
  workItem: WorkItemRef | null;
  machine: string;
  session: string;
  terminal: string | null;
  resumeCommand: string;
  selected?: boolean;
  onCopy?: (text: string) => void;
  onOpen?: () => void;
}

/** One entry in the Needs you inbox. */
export function NeedsYouCard(p: NeedsYouCardProps) {
  const [title, icon] = p.reason ? REASON[p.reason.kind] : UNKNOWN_REASON;
  return (
    <article className={`ncard${p.selected ? " sel" : ""}`} aria-label={`${title} from ${p.session}`}>
      <header>
        <Icon name={icon} size="18px" />
        {title}
        <span className="wait">{formatDuration(p.waitingMs)}</span>
      </header>
      <div className="nb">
        <span className="nwhat">
          <b>{p.repo}</b> · {p.kind ?? <Unknown />} · <WorkItemLink item={p.workItem} />
        </span>
        <NeedsBody reason={p.reason} />
        <dl className="where">
          <div><dt>Machine</dt><dd>{p.machine}</dd></div>
          <div><dt>Session</dt><dd>{p.session}</dd></div>
          <div><dt>Terminal</dt><dd>{p.terminal ?? <Unknown />}</dd></div>
        </dl>
        <div className="nact">
          <button type="button" className="btn btn-needs" onClick={() => p.onCopy?.(p.resumeCommand)}>
            <Icon name="terminal" />
            Copy resume command
          </button>
          <button type="button" className="btn" onClick={p.onOpen}>
            Open detail <Icon name="arrow" />
          </button>
        </div>
      </div>
    </article>
  );
}

export interface DoneCardProps {
  /** Session kind; null while unknown. */
  kind: string | null;
  workItem: WorkItemRef | null;
  repo: string;
  machine: string;
  agoMs: number;
  now: string | null;
  onOpen?: () => void;
}

/** One Done-unseen entry under the inbox. It becomes seen when the human opens it or types into the session. */
export function DoneCard(p: DoneCardProps) {
  return (
    <div className="dcard">
      <span className="dt">{p.kind ?? <Unknown />} · <WorkItemLink item={p.workItem} /></span>
      <span className="dm">{p.repo} · {p.machine} · {formatDuration(p.agoMs)} ago</span>
      <NowLine now={p.now} />
      <div className="nact">
        <button type="button" className="btn" onClick={p.onOpen}>Open</button>
      </div>
    </div>
  );
}

/** The dashboard's left panel: the Needs you inbox, then Done-unseen. */
export function Inbox({ children }: { children: ReactNode }) {
  return (
    <section className="inbox" aria-label="Needs you and Done unseen">
      {children}
    </section>
  );
}

export function InboxHeader({ count }: { count: number }) {
  return (
    <div className="inbox-h">
      <span className={`n${count ? "" : " zero"}`}>{count}</span>
      <div>
        <h2>Needs you</h2>
        <p>Oldest first. Each one is a session waiting on you.</p>
      </div>
    </div>
  );
}
