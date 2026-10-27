import { useMemo, useState } from "react";
import { decisionName, mapGraph, type DecisionTicketData, type MapData, type WayfinderData } from "../wayfinder";
import { GraphView } from "./Graph";
import { WorkItemLink } from "./InboxCards";
import { Panel } from "./Panel";
import { Detail, Facts, Hint, SessionHeader, Timeline, type SessionHeaderProps, type TimelineEntry } from "./SessionDetail";
import { Tag } from "./Tag";
import { Unknown } from "./Unknown";

export interface WayfinderViewProps extends Omit<SessionHeaderProps, "title"> {
  /** What the session does on its Map; null until the server has seen it start. */
  plan: WayfinderData | null;
  /** The session's Map as last polled; null until known. */
  map: MapData | null;
  actions: TimelineEntry[];
}

function TicketLink({ t }: { t: DecisionTicketData }) {
  return <a className="wi" href={t.url}>{decisionName(t)}</a>;
}

/** A ticket the Map knows by name, else by number. */
function TicketRef({ number, map }: { number: number; map: MapData | null }) {
  const t = map?.tickets.find((x) => x.number === number);
  return t ? <TicketLink t={t} /> : <span className="mono">#{number}</span>;
}

/**
 * A Wayfinder session: its Map drawn as a graph with its fog, the Destination, the Decision ticket being worked and
 * its current question, and the decisions recorded and tickets created or closed this session.
 */
export function WayfinderView({ plan, map, actions, ...header }: WayfinderViewProps) {
  const [selected, setSelected] = useState<string>();
  const needs = header.state === "Needs you";
  const items = useMemo(() => (map ? mapGraph(map, { ticket: plan?.ticket ?? null, needs }) : []), [map, plan?.ticket, needs]);
  const working = plan?.ticket != null ? map?.tickets.find((t) => t.number === plan.ticket) : undefined;
  const pick = map?.tickets.find((t) => String(t.number) === selected);
  const closed = plan?.closed ?? [];
  const created = plan?.created ?? [];
  return (
    <Detail label="Wayfinder session detail">
      <SessionHeader {...header} title={map ? <WorkItemLink item={{ name: decisionName(map), url: map.url }} /> : plan?.map ? `#${plan.map}` : <Unknown />} />
      <Panel title="Destination">
        {map?.destination ? <p className="prose">{map.destination}</p> : <Unknown />}
      </Panel>
      <Panel title="Decision ticket">
        <Facts
          items={[
            ["Working", plan?.ticket != null ? <TicketRef number={plan.ticket} map={map} /> : <Unknown />],
            ["Type", working?.type ? <><Tag>{working.type}</Tag> <Tag>{working.mode ?? "—"}</Tag></> : <Unknown />],
            ["Current question", plan?.questions.length ? (
              <ul className="files">{plan.questions.map((q) => <li key={q}>{q}</li>)}</ul>
            ) : <Unknown />],
          ]}
        />
      </Panel>
      <Panel title={map ? "Map" : "Map — not polled yet"}>
        {map && items.length ? (
          <GraphView items={items} fog={map.fog} selectedId={selected} onSelect={setSelected} label={`Map: ${map.title}`} />
        ) : map ? (
          <Hint>No Decision tickets on this Map yet.</Hint>
        ) : (
          <Hint>The Map appears once the server reads it from GitHub.</Hint>
        )}
      </Panel>
      {pick && map ? <DecisionPanel t={pick} map={map} /> : map && items.length ? <Hint>Select a Decision ticket to see its decision, dependencies and claim.</Hint> : null}
      <Panel title={`Decisions recorded this session · ${closed.length}`}>
        {closed.length ? (
          <ul className="files">
            {closed.map((n) => (
              <li key={n}><TicketRef number={n} map={map} />{" "}<span className="muted">{map?.tickets.find((t) => t.number === n)?.gist ?? "—"}</span></li>
            ))}
          </ul>
        ) : <Hint>None yet.</Hint>}
      </Panel>
      <Panel title="Tickets this session">
        <Facts
          items={[
            [`Created ${created.length}`, created.length ? <>{created.map((n, i) => <span key={n}>{i ? ", " : ""}<TicketRef number={n} map={map} /></span>)}</> : "none"],
            [`Closed ${closed.length}`, closed.length ? <>{closed.map((n, i) => <span key={n}>{i ? ", " : ""}<TicketRef number={n} map={map} /></span>)}</> : "none"],
          ]}
        />
      </Panel>
      <Panel title={actions.length ? `Last ${actions.length} actions` : "Last actions"}>
        {actions.length ? <Timeline actions={actions} /> : <Hint>No actions yet.</Hint>}
      </Panel>
    </Detail>
  );
}

function DecisionPanel({ t, map }: { t: DecisionTicketData; map: MapData }) {
  const unblocks = map.tickets.filter((x) => x.blockedBy.includes(t.number));
  const state = t.state === "closed" ? "closed" : t.assignees.length ? `claimed by ${t.assignees.join(", ")}` : "open";
  return (
    <Panel title={<>Decision ticket · <TicketLink t={t} /></>} label="Decision ticket detail">
      <Facts
        items={[
          ["Type", <><Tag>{t.type ?? "type unknown"}</Tag> <Tag>{t.mode ?? "—"}</Tag></>],
          ["State", state],
          ["Decision", t.gist ?? <Unknown />],
          ["Depends on", t.blockedBy.length ? <>{t.blockedBy.map((n, i) => <span key={n}>{i ? ", " : ""}<TicketRef number={n} map={map} /></span>)}</> : "nothing"],
          ["Unblocks", unblocks.length ? <>{unblocks.map((u, i) => <span key={u.number}>{i ? ", " : ""}<TicketLink t={u} /></span>)}</> : "nothing"],
        ]}
      />
    </Panel>
  );
}
