import { useEffect, useState } from "react";
import { FlowStrip, SessionTable, TopBar, type SessionState } from "../ds";

/** The server's dashboard state (GET /api/state, and each SSE `state` event). */
interface FactoryState {
  server_version: string;
  /** Tracked repos, each with the Machines that track it. */
  repos: { repo: string; machines: string[] }[];
  sessions: { id: string; machine: string; repo: string; state: SessionState; state_since: string }[];
}

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

export function Dashboard() {
  const state = useFactoryState();
  const now = useNow(1000);
  const sessions = state?.sessions.map((s) => ({ ...s, inStateMs: now - Date.parse(s.state_since) }));
  return (
    <>
      <TopBar />
      <main className="page">
        {state ? <FlowStrip rows={state.repos.map((r) => ({ repo: r.repo, chips: [] }))} /> : null}
        {sessions ? <SessionTable sessions={sessions} /> : null}
      </main>
    </>
  );
}
