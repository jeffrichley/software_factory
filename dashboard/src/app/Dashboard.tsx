import { useEffect, useRef, useState } from "react";
import {
  AdHocView,
  DoneCard,
  DoneUnseenCount,
  Empty,
  FlowStrip,
  HIDDEN_MACHINES_KEY,
  HiddenNeedsBadge,
  Icon,
  Inbox,
  InboxHeader,
  MachinePill,
  MachinePills,
  NeedsCount,
  NeedsYouCard,
  SectionHeading,
  SessionTable,
  SoundToggle,
  SPEC_JOB,
  SpecJobView,
  Split,
  TICKET_JOB,
  TicketJobView,
  TopBar,
  filterUrl,
  flowRows,
  hiddenMachinesOf,
  currentJob,
  inboxOf,
  type JobData,
  newSounds,
  playSound,
  resumeCommand,
  viewOf,
  type NeedsReason,
  type SessionRowData,
  type SessionState,
  type SoundName,
  type StepPhase,
  type TimelineEntry,
} from "../ds";

/** The server's dashboard state (GET /api/state, and each SSE `state` event). */
interface FactoryState {
  server_version: string;
  /** Machines that track a repo or have a live session; a silent one has sent nothing for a while. */
  machines: { machine: string; sessions: number; last_seen: string; silent: boolean }[];
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
    /** A Working session on a silent Machine is Stale, with stale_reason "Machine silent". */
    stale_reason?: string;
    /** Why it Needs you; null otherwise. */
    reason: NeedsReason | null;
    /** Done has been seen. */
    seen: boolean;
    /** Hidden by the human (/factory:hide or the dashboard): out of every view, and silent. */
    hidden: boolean;
    kind: string;
    /** The skill that gave the session its kind. */
    skill: string | null;
    /** The latest skill the skill table doesn't know. */
    unknown_skill: string | null;
    now: string | null;
    /** The last few actions, oldest first. */
    actions: TimelineEntry[];
  }[];
  /** Jobs in Tracked repos, oldest first. */
  jobs: {
    id: string;
    session_id: string;
    kind: string;
    repo: string;
    number: number | null;
    work_item: { title: string; url: string } | null;
    worktree: string | null;
    branch: string | null;
    stage: string;
    pr: { number: number | null; url: string; draft: boolean } | null;
    started_at: string;
  }[];
  /** Steps of those Jobs, oldest first: a Ticket Job has one, a Spec Job one per Ticket of its Spec. */
  steps: {
    id: string;
    job_id: string;
    session_id: string;
    repo: string;
    number: number | null;
    title: string | null;
    /** null = Phase unknown; Pending = a Spec Job's Step not started yet. */
    phase: StepPhase;
    phase_since: string;
    /** The Tickets that block this one. */
    blocked_by: number[];
  }[];
  /** The latest sounds the server has played, one per transition; ids only grow. */
  sounds: { id: number; session_id: string; machine: string; sound: SoundName; at: string }[];
}

type Session = SessionRowData & {
  ccSessionId: string;
  reason: NeedsReason | null;
  seen: boolean;
  hidden: boolean;
  actions: TimelineEntry[];
};

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

const SOUND_KEY = "factory.sound";

/** The header's sound toggle, remembered in this browser; on unless turned off. */
function useSoundOn(): [boolean, () => void] {
  const [on, setOn] = useState(() => {
    try {
      return localStorage.getItem(SOUND_KEY) !== "off";
    } catch {
      return true;
    }
  });
  const toggle = () =>
    setOn((was) => {
      try {
        localStorage.setItem(SOUND_KEY, was ? "off" : "on");
      } catch {
        // Not remembered; the toggle still works for this page.
      }
      return !was;
    });
  return [on, toggle];
}

/** Plays each sound the server adds, once; none from before the page opened, none while muted. */
function useSounds(sounds: FactoryState["sounds"] | undefined, on: boolean): void {
  const heard = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (!sounds) return;
    const next = newSounds(sounds, heard.current);
    heard.current = next.heard;
    if (on) next.play.forEach((s) => playSound(s.sound));
  }, [sounds, on]);
}

const copy = (text: string) => void navigator.clipboard?.writeText(text).catch(() => {});

/** The Machines the browser remembers hiding; storage can be blocked, so it is only ever a convenience. */
function rememberedHiddenMachines(): string[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(HIDDEN_MACHINES_KEY) ?? "[]");
    return Array.isArray(stored) ? stored.filter((m): m is string => typeof m === "string") : [];
  } catch {
    return [];
  }
}

/** The Machine filter, remembered in the browser and in ?machines= (the URL wins when the page loads). */
function useMachineFilter(names: string[]): [string[], (hidden: string[]) => void] {
  // Until the human toggles a pill, the filter comes from the URL or the browser, applied to the Machines known now.
  const [chosen, setChosen] = useState<string[] | null>(null);
  const hidden = chosen ?? hiddenMachinesOf(names, window.location.search, rememberedHiddenMachines());
  const choose = (next: string[]) => {
    setChosen(next);
    try {
      localStorage.setItem(HIDDEN_MACHINES_KEY, JSON.stringify(next));
    } catch {
      // remembered in the URL only
    }
    window.history.replaceState(null, "", filterUrl(window.location.href, names, next));
  };
  return [hidden, choose];
}

/** How much of a Claude Code session id a card shows; the resume command carries all of it. */
const SESSION_ID_CHARS = 8;

export function Dashboard() {
  const state = useFactoryState();
  const now = useNow(1000);
  const [selectedId, setSelectedId] = useState<string>();
  const [showHiddenSessions, setShowHiddenSessions] = useState(false);
  const names = state?.machines.map((m) => m.machine) ?? [];
  const [hiddenMachines, setHiddenMachines] = useMachineFilter(names);
  const [soundOn, toggleSound] = useSoundOn();
  useSounds(state?.sounds, soundOn);
  const sessions: Session[] = state?.sessions.map((s) => ({
    id: s.id, machine: s.machine, repo: s.repo, ccSessionId: s.cc_session_id, state: s.state, staleReason: s.stale_reason, reason: s.reason,
    seen: s.seen, hidden: s.hidden, kind: s.kind, unknownSkill: s.unknown_skill, now: s.now, actions: s.actions,
    inStateMs: now - Date.parse(s.state_since),
  })) ?? [];
  const view = viewOf(sessions, hiddenMachines);
  const selected = [...view.shown, ...view.hiddenSessions].find((s) => s.id === selectedId);
  const { needs, doneUnseen } = inboxOf(view.shown);
  // A repo shows while any Machine that tracks it does.
  const repos = state?.repos.filter((r) => r.machines.some((m) => !hiddenMachines.includes(m)));
  const toggleMachine = (m: string) =>
    setHiddenMachines(hiddenMachines.includes(m) ? hiddenMachines.filter((h) => h !== m) : [...hiddenMachines, m]);
  const showMachines = (ms: string[]) => setHiddenMachines(hiddenMachines.filter((h) => !ms.includes(h)));
  const setHidden = (id: string, hidden: boolean) =>
    void fetch(`/api/sessions/${id}/${hidden ? "hide" : "show"}`, { method: "POST" }).catch(() => {});
  const jobs: JobData[] = (state?.jobs ?? []).map((j) => ({
    id: j.id, sessionId: j.session_id, kind: j.kind, number: j.number, stage: j.stage, branch: j.branch,
    worktree: j.worktree, pr: j.pr, workItem: j.work_item && { name: j.work_item.title, url: j.work_item.url },
  }));
  const jobOf = (sessionId: string) => currentJob(jobs, sessionId);
  const steps = (state?.steps ?? []).map((s) => ({
    id: s.id, jobId: s.job_id, sessionId: s.session_id, repo: s.repo, number: s.number, title: s.title, phase: s.phase,
    phaseSince: s.phase_since, blockedBy: s.blocked_by,
  }));
  const stepsOf = (job: JobData | null) => (job ? steps.filter((s) => s.jobId === job.id) : []);
  const flow = flowRows(repos?.map((r) => r.repo) ?? [], view.shown, jobs, steps).map((r) => ({
    repo: r.repo,
    chips: r.chips.map(({ sessionId, ...c }) => ({ ...c, selected: sessionId === selectedId, onOpen: () => open(sessionId) })),
  }));
  const workItemOf = (sessionId: string) => jobOf(sessionId)?.workItem ?? null;

  const seen = (id: string) => void fetch(`/api/sessions/${id}/seen`, { method: "POST" }).catch(() => {});
  /** Opening a session's detail, from its row or its inbox card, makes its Done seen. */
  const open = (id: string) => {
    setSelectedId(id);
    seen(id);
  };

  return (
    <>
      <TopBar>
        <MachinePills>
          {state?.machines.map((m) => (
            <MachinePill
              key={m.machine}
              name={m.machine}
              sessions={m.sessions}
              silentForMs={m.silent ? now - Date.parse(m.last_seen) : undefined}
              hidden={hiddenMachines.includes(m.machine)}
              onToggle={() => toggleMachine(m.machine)}
            />
          ))}
        </MachinePills>
        <div className="counts">
          <HiddenNeedsBadge count={view.hiddenNeeds.length} onShow={() => showMachines(view.hiddenNeeds.map((s) => s.machine))} />
          <NeedsCount count={needs.length} />
          <DoneUnseenCount count={doneUnseen.length} />
          <SoundToggle on={soundOn} onToggle={toggleSound} />
        </div>
      </TopBar>
      <Split
        side={
          <Inbox>
            <InboxHeader count={needs.length} />
            {needs.length ? (
              needs.map((s) => (
                <NeedsYouCard
                  key={s.id}
                  reason={s.reason}
                  waitingMs={s.inStateMs}
                  repo={s.repo}
                  kind={s.kind}
                  workItem={workItemOf(s.id)}
                  machine={s.machine}
                  session={s.ccSessionId.slice(0, SESSION_ID_CHARS)}
                  terminal={null}
                  resumeCommand={resumeCommand(s.ccSessionId)}
                  selected={s.id === selectedId}
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
                  kind={s.kind}
                  workItem={workItemOf(s.id)}
                  repo={s.repo}
                  machine={s.machine}
                  agoMs={s.inStateMs}
                  now={s.now}
                  onOpen={() => open(s.id)}
                />
              ))
            ) : (
              <Empty>Everything Done has been seen.</Empty>
            )}
          </Inbox>
        }
      >
        {repos ? <FlowStrip rows={flow} /> : null}
        {state ? (
          <SessionTable
            sessions={showHiddenSessions ? [...view.shown, ...view.hiddenSessions] : view.shown}
            selectedId={selectedId}
            onSelect={open}
          />
        ) : null}
        {view.hiddenSessions.length ? (
          <div className="toolbar">
            <button type="button" className={`btn${showHiddenSessions ? " btn-on" : ""}`} aria-pressed={showHiddenSessions} onClick={() => setShowHiddenSessions(!showHiddenSessions)}>
              {showHiddenSessions ? "Leave out" : "List"} {view.hiddenSessions.length} hidden session(s)
            </button>
          </div>
        ) : null}
        {selected ? (
          <div className="toolbar">
            <button type="button" className="btn" onClick={() => setHidden(selected.id, !selected.hidden)}>
              {selected.hidden ? "Show this session" : "Hide this session"}
            </button>
          </div>
        ) : null}
        {/* Kinds without their own detail view yet show the ad hoc view, titled by their kind. */}
        {selected ? (
          selected.kind === TICKET_JOB ? (
            <TicketJobView {...selected} job={jobOf(selected.id)} />
          ) : selected.kind === SPEC_JOB ? (
            <SpecJobView key={selected.id} {...selected} job={jobOf(selected.id)} steps={stepsOf(jobOf(selected.id))} nowMs={now} />
          ) : (
            <AdHocView {...selected} />
          )
        ) : null}
      </Split>
    </>
  );
}
