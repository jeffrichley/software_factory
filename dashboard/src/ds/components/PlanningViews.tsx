import { useMemo, useState } from "react";
import { createdTicketName, outlineProgress, ticketsGraph, type ResearchData, type ToSpecData, type ToTicketsData } from "../planning";
import { GraphView } from "./Graph";
import { Icon } from "./Icon";
import { WorkItemLink, type WorkItemRef } from "./InboxCards";
import { Panel } from "./Panel";
import { Detail, Facts, Hint, SessionHeader, Timeline, type SessionHeaderProps, type TimelineEntry } from "./SessionDetail";
import { Unknown } from "./Unknown";

type HeaderProps = Omit<SessionHeaderProps, "title">;

function LastActions({ actions }: { actions: TimelineEntry[] }) {
  return (
    <Panel title={actions.length ? `Last ${actions.length} actions` : "Last actions"}>
      {actions.length ? <Timeline actions={actions} /> : <Hint>No actions yet.</Hint>}
    </Panel>
  );
}

export interface ResearchViewProps extends HeaderProps {
  /** What the session has read; null until the server has seen it start. */
  research: ResearchData | null;
  actions: TimelineEntry[];
}

/** A research session: its question, the searches run, the sources fetched and its findings file. */
export function ResearchView({ research, actions, ...header }: ResearchViewProps) {
  const searches = research?.searches ?? [];
  const sources = research?.sources ?? [];
  const findings = research?.findings ?? null;
  return (
    <Detail label="research session detail">
      <SessionHeader {...header} title="Research" />
      <Panel title="Question">
        {research?.question ? <p className="prose needs-q">{research.question}</p> : <Unknown />}
      </Panel>
      <div className="plan-grid">
        <Panel title={`Searches run · ${searches.length}`}>
          {searches.length ? (
            <ol className="files plan-list">{searches.map((q, i) => <li key={`${q}-${i}`}><Icon name="search" /><span className="mono">{q}</span></li>)}</ol>
          ) : <Hint>None yet.</Hint>}
        </Panel>
        <Panel title={`Sources fetched · ${sources.length}`}>
          {sources.length ? (
            <ul className="files plan-list">{sources.map((u) => <li key={u}><a className="wi mono" href={u}>{u}</a></li>)}</ul>
          ) : <Hint>None yet.</Hint>}
        </Panel>
      </div>
      <Panel title="Findings file">
        {findings ? (
          findings.url ? <a className="wi mono" href={findings.url}>{findings.path}</a> : <span className="mono">{findings.path}</span>
        ) : <><Unknown /> <span className="hint">not written yet</span></>}
      </Panel>
      <LastActions actions={actions} />
    </Detail>
  );
}

export interface ToSpecViewProps extends HeaderProps {
  /** What the session has written; null until the server has seen it start. */
  toSpec: ToSpecData | null;
  /** The Map it came from, and the Spec it published; null until known. */
  map: WorkItemRef | null;
  spec: WorkItemRef | null;
  actions: TimelineEntry[];
}

/** A to-spec session: the Map it came from and the Spec outline, ticked as each section is written. */
export function ToSpecView({ toSpec, map, spec, actions, ...header }: ToSpecViewProps) {
  const outline = toSpec?.outline ?? [];
  const progress = outlineProgress(outline);
  return (
    <Detail label="to-spec session detail">
      <SessionHeader {...header} title={spec ? <WorkItemLink item={spec} /> : "Spec being written"} />
      <div className="plan-grid">
        <Panel title="From Map">
          <WorkItemLink item={map} />
        </Panel>
        <Panel title="Spec created">
          {spec ? <WorkItemLink item={spec} /> : <><Unknown /> <span className="hint">not published yet</span></>}
        </Panel>
      </div>
      <Panel title={`Spec outline · ${progress.written} / ${progress.total} sections`}>
        <ul className="checklist" aria-label="Spec outline">
          {outline.map((o, i) => (
            <li key={o.section} className={o.written ? "done" : i === progress.current ? "cur" : ""}>
              <span className="cb" aria-hidden="true">{o.written ? <Icon name="check" size="12px" /> : null}</span>
              <span>{o.section}{i === progress.current ? " — writing now" : ""}</span>
            </li>
          ))}
        </ul>
      </Panel>
      <LastActions actions={actions} />
    </Detail>
  );
}

export interface ToTicketsViewProps extends HeaderProps {
  /** What the session has created; null until the server has seen it start. */
  toTickets: ToTicketsData | null;
  /** The Spec it breaks into Tickets; null until known. */
  spec: WorkItemRef | null;
  actions: TimelineEntry[];
}

/** A to-tickets session: the Tickets it created, drawn as a graph in the one graph style, all not started. */
export function ToTicketsView({ toTickets, spec, actions, ...header }: ToTicketsViewProps) {
  const [selected, setSelected] = useState<string>();
  const tickets = toTickets?.tickets ?? [];
  const items = useMemo(() => ticketsGraph(tickets), [tickets]);
  const pick = tickets.find((t) => String(t.number) === selected);
  const nameOf = (n: number) => {
    const t = tickets.find((x) => x.number === n);
    return t ? <a className="wi" href={t.url}>{createdTicketName(t)}</a> : <span className="mono">#{n}</span>;
  };
  const list = (ns: number[]) => (ns.length ? <>{ns.map((n, i) => <span key={n}>{i ? ", " : ""}{nameOf(n)}</span>)}</> : "nothing");
  return (
    <Detail label="to-tickets session detail">
      <SessionHeader {...header} title={spec ? <WorkItemLink item={spec} /> : <Unknown />} />
      <Panel title={`Tickets created · ${tickets.length}`}>
        {items.length ? (
          <GraphView items={items} selectedId={selected} onSelect={setSelected} label={`Tickets created from ${spec?.name ?? "the Spec"}`} />
        ) : <Hint>No Tickets created yet.</Hint>}
      </Panel>
      {pick ? (
        <Panel title={<>Ticket · <a className="wi" href={pick.url}>{createdTicketName(pick)}</a></>} label="Ticket detail">
          <Facts
            items={[
              ["State", "not started"],
              ["Depends on", list(pick.blockedBy)],
              ["Unblocks", list(tickets.filter((t) => t.blockedBy.includes(pick.number)).map((t) => t.number))],
            ]}
          />
        </Panel>
      ) : items.length ? <Hint>Select a Ticket for its dependencies. No Ticket has a Job yet.</Hint> : null}
      <LastActions actions={actions} />
    </Detail>
  );
}
