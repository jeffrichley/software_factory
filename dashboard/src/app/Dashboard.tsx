import { useEffect, useState } from "react";
import {
  Detail, FlowStrip, Hint, Panel, SessionHeader, SessionTable, Timeline, TopBar, type SessionRowData, type SessionState, type TimelineEntry,
} from "../ds";

/** The server's dashboard state (GET /api/state, and each SSE `state` event). */
interface FactoryState {
  server_version: string;
  /** Tracked repos, each with the Machines that track it. */
  repos: { repo: string; machines: string[] }[];
  sessions: {
    id: string;
    machine: string;
    repo: string;
    state: SessionState;
    state_since: string;
    kind: string;
    skill: string | null;
    now: string | null;
    /** The last few actions, oldest first. */
    actions: TimelineEntry[];
  }[];
}

type Session = FactoryState["sessions"][number] & SessionRowData;

/** Live dashboard state: the SSE stream sends the full state on connect and on every change. */
function useFactoryState(): FactoryState | null {
  const [state, setState] = useState<FactoryState | null>(null);
  useEffect(() => {
    const source = new EventSource("/api/stream");
    source.addEventListener("state", (e) => setState(JSON.parse((e as MessageEvent<string>).data)));
    return () => source.close();
  }, []);
  return state;
}

function useNow(everyMs: number): number {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(t);
  }, [everyMs]);
  return now;
}

/** Ad hoc sessions run no skill the Factory knows, so there is no Job, Step or Phase: state, headline, last actions. */
function AdHocView({ s }: { s: Session }) {
  return (
    <Detail label="Session detail">
      <SessionHeader {...s} title={s.skill ? <>Ad hoc session · running skill <code className="mono">{s.skill}</code></> : "Ad hoc session"} />
      <Panel title={s.actions.length ? `Last ${s.actions.length} actions` : "Last actions"}>
        {s.actions.length ? <Timeline actions={s.actions} /> : <Hint>No actions yet.</Hint>}
      </Panel>
      <Hint>Ad hoc sessions run no skill the Factory knows, so there is no Job, Step or Phase.</Hint>
    </Detail>
  );
}

export function Dashboard() {
  const state = useFactoryState();
  const now = useNow(1000);
  const [selectedId, setSelectedId] = useState<string>();
  const sessions: Session[] | undefined = state?.sessions.map((s) => ({ ...s, inStateMs: now - Date.parse(s.state_since) }));
  const selected = sessions?.find((s) => s.id === selectedId);
  return (
    <>
      <TopBar />
      <main className="page">
        {state ? <FlowStrip rows={state.repos.map((r) => ({ repo: r.repo, chips: [] }))} /> : null}
        {sessions ? <SessionTable sessions={sessions} selectedId={selectedId} onSelect={setSelectedId} /> : null}
        {/* Every kind shows the ad hoc view until its own detail view arrives. */}
        {selected ? <AdHocView s={selected} /> : null}
      </main>
    </>
  );
}
