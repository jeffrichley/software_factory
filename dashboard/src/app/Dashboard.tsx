import { useEffect, useState } from "react";
import {
  DoneCard,
  Empty,
  FlowStrip,
  Icon,
  Inbox,
  InboxHeader,
  NeedsYouCard,
  SectionHeading,
  SessionTable,
  Split,
  TopBar,
  inboxOf,
  resumeCommand,
  type NeedsReason,
  type SessionState,
} from "../ds";

/** The server's dashboard state (GET /api/state, and each SSE `state` event). */
interface FactoryState {
  server_version: string;
  /** Tracked repos, each with the Machines that track it. */
  repos: { repo: string; machines: string[] }[];
  /** Live Tracked sessions, Needs you first. */
  sessions: {
    id: string;
    machine: string;
    repo: string;
    cc_session_id: string;
    state: SessionState;
    state_since: string;
    /** Why it Needs you; null otherwise. */
    reason: NeedsReason | null;
    /** Done has been seen. */
    seen: boolean;
  }[];
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

const copy = (text: string) => void navigator.clipboard?.writeText(text).catch(() => {});

export function Dashboard() {
  const state = useFactoryState();
  const now = useNow(1000);
  const [selected, setSelected] = useState<string | null>(null);
  const sessions = state?.sessions.map((s) => ({ ...s, inStateMs: now - Date.parse(s.state_since) }));
  const { needs, doneUnseen } = inboxOf(sessions ?? []);

  /** Opening a session's detail makes its Done seen (the detail view itself comes with session kinds). */
  const open = (id: string) => {
    setSelected(id);
    void fetch(`/api/sessions/${id}/seen`, { method: "POST" }).catch(() => {});
  };
  const seen = (id: string) => void fetch(`/api/sessions/${id}/seen`, { method: "POST" }).catch(() => {});

  return (
    <>
      <TopBar />
      <Split
        side={
          <Inbox>
            <InboxHeader count={needs.length} />
            {needs.length ? (
              needs.map((s) => (
                <NeedsYouCard
                  key={s.id}
                  reason={s.reason ?? { kind: "question", text: "" }}
                  waitingMs={s.inStateMs}
                  repo={s.repo}
                  kind={null}
                  workItem={null}
                  machine={s.machine}
                  session={s.cc_session_id.slice(0, 8)}
                  terminal={null}
                  resumeCommand={resumeCommand(s.cc_session_id)}
                  selected={s.id === selected}
                  onCopy={copy}
                  onOpen={() => open(s.id)}
                />
              ))
            ) : (
              <Empty><Icon name="check" /> Nothing needs you. New questions and permission prompts land here.</Empty>
            )}
            <SectionHeading icon="check" tone="done">Done — unseen · {doneUnseen.length}</SectionHeading>
            {doneUnseen.length ? (
              doneUnseen.map((s) => (
                <DoneCard
                  key={s.id}
                  kind={null}
                  workItem={null}
                  repo={s.repo}
                  machine={s.machine}
                  agoMs={s.inStateMs}
                  now={null}
                  onOpen={() => open(s.id)}
                  onSeen={() => seen(s.id)}
                />
              ))
            ) : (
              <Empty>Everything Done has been seen.</Empty>
            )}
          </Inbox>
        }
      >
        {state ? <FlowStrip rows={state.repos.map((r) => ({ repo: r.repo, chips: [] }))} /> : null}
        {sessions ? <SessionTable sessions={sessions} /> : null}
      </Split>
    </>
  );
}
