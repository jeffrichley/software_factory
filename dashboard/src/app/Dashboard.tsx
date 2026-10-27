import { type ReactNode, useEffect, useRef, useState } from "react";
import {
  AdHocView,
  DoneCard,
  DoneUnseenCount,
  Empty,
  FlowStrip,
  HIDDEN_MACHINES_KEY,
  HiddenNeedsBadge,
  HistoryCount,
  HistoryList,
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
  WAYFINDER,
  WayfinderView,
  RESEARCH,
  ResearchView,
  TO_SPEC,
  ToSpecView,
  TO_TICKETS,
  ToTicketsView,
  type ResearchData,
  type ToSpecData,
  type ToTicketsData,
  type DecisionTicketData,
  type MapData,
  type WayfinderData,
  filterUrl,
  flowRows,
  hiddenMachinesOf,
  currentJob,
  historyOf,
  inboxOf,
  type JobData,
  newSounds,
  ReplayView,
  type ReplayData,
  playSound,
  resumeCommand,
  viewOf,
  type NeedsReason,
  type SessionRowData,
  type SessionState,
  type SoundName,
  type StepDetailData,
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
  /** Work items of Tracked repos as last polled. */
  work_items: { repo: string; number: number; title: string; state: string; url: string; kind: string }[];
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
    /** A Working session with no events of its own for a while (its Machine still reporting): since its last one; null otherwise. */
    quiet_since: string | null;
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
    /** The Machine its session runs on. */
    machine: string;
    kind: string;
    repo: string;
    number: number | null;
    work_item: { title: string; url: string } | null;
    worktree: string | null;
    branch: string | null;
    stage: string;
    pr: { number: number | null; url: string; draft: boolean } | null;
    started_at: string;
    /** The active Job already on its Work item when it started; flagged, not blocked. */
    duplicate_of: string | null;
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
  /** Live Wayfinder sessions: the Map, the Decision ticket worked, the current round's question titles, and the
   * tickets created and closed this session. */
  wayfinder: { session_id: string; map: number | null; ticket: number | null; questions: string[]; created: number[]; closed: number[] }[];
  /** Maps in Tracked repos, with their Destination, fog and Decision tickets (Out of scope left out). */
  maps: {
    repo: string;
    number: number;
    title: string;
    url: string;
    destination: string | null;
    fog: string[];
    tickets: {
      number: number; title: string; url: string; state: "open" | "closed"; type: string | null; mode: string | null;
      assignees: string[]; gist: string | null; blocked_by: number[];
    }[];
  }[];
  /** What each Step has done, by Step id. */
  step_details: Record<string, {
    phase_events: { at: string; from: string | null; to: string | null }[];
    tests: StepDetailData["tests"];
    files: StepDetailData["files"];
    commits: StepDetailData["commits"];
    pr: StepDetailData["pr"];
    review: StepDetailData["review"];
    checklist: StepDetailData["checklist"];
    struggle: { failures: number | null; churn: string[]; silent_for_s: number | null } | null;
  }>;
  /** Code-review findings on a whole Job (a Spec Job's integration branch), by Job id. */
  job_reviews: Record<string, NonNullable<StepDetailData["review"]>>;
  /** Live research sessions: the question, searches run, sources fetched and findings file. */
  research: { session_id: string; question: string | null; searches: string[]; sources: string[]; findings: { path: string; url: string | null } | null }[];
  /** Live to-spec sessions: the Map they came from, the Spec they published and the Spec outline, ticked as written. */
  to_spec: { session_id: string; map: number | null; spec: number | null; outline: { section: string; written: boolean }[] }[];
  /** Live to-tickets sessions: their Spec and the Tickets they created, as GitHub last had them. */
  to_tickets: {
    session_id: string;
    spec: number | null;
    tickets: { number: number; title: string | null; url: string; state: "open" | "closed"; blocked_by: number[] }[];
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

/** A Job's timeline for its replay, fetched once when it opens; null while loading (or if it can't be read). */
function useReplay(jobId: string | undefined): ReplayData | null {
  const [replay, setReplay] = useState<ReplayData | null>(null);
  useEffect(() => {
    setReplay(null);
    if (!jobId) return;
    let live = true;
    fetch(`/api/jobs/${jobId}/replay`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: ReplayData | null) => { if (live) setReplay(data); })
      .catch(() => {});
    return () => { live = false; };
  }, [jobId]);
  return replay;
}

/** How much of a Claude Code session id a card shows; the resume command carries all of it. */
const SESSION_ID_CHARS = 8;

export function Dashboard() {
  const state = useFactoryState();
  const now = useNow(1000);
  const [selectedId, setSelectedId] = useState<string>();
  // The Step opened with the session, from its flow-strip chip; none when opened from its row or card.
  const [selectedStepId, setSelectedStepId] = useState<string>();
  const [showHiddenSessions, setShowHiddenSessions] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [replayId, setReplayId] = useState<string>();
  const replay = useReplay(replayId);
  const names = state?.machines.map((m) => m.machine) ?? [];
  const [hiddenMachines, setHiddenMachines] = useMachineFilter(names);
  const [soundOn, toggleSound] = useSoundOn();
  useSounds(state?.sounds, soundOn);
  const sessions: Session[] = state?.sessions.map((s) => ({
    id: s.id, machine: s.machine, repo: s.repo, ccSessionId: s.cc_session_id, state: s.state, staleReason: s.stale_reason, reason: s.reason,
    seen: s.seen, hidden: s.hidden, kind: s.kind, unknownSkill: s.unknown_skill, now: s.now, actions: s.actions,
    inStateMs: now - Date.parse(s.state_since),
    ...(s.quiet_since ? { quietMs: now - Date.parse(s.quiet_since) } : {}),
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
    id: j.id, sessionId: j.session_id, machine: j.machine, kind: j.kind, repo: j.repo, startedAt: j.started_at, duplicateOf: j.duplicate_of,
    number: j.number, stage: j.stage, branch: j.branch,
    worktree: j.worktree, pr: j.pr, workItem: j.work_item && { name: j.work_item.title, url: j.work_item.url },
  }));
  const history = historyOf(jobs, hiddenMachines);
  // A replay of a Job on a Machine hidden since closes with it.
  const replayJob = history.find((j) => j.id === replayId);
  const abandon = (jobId: string) => {
    if (window.confirm(`Mark Job ${jobId} abandoned? It moves to History.`)) {
      void fetch(`/api/jobs/${jobId}/abandon`, { method: "POST" }).catch(() => {});
    }
  };
  const jobOf = (sessionId: string) => currentJob(jobs, sessionId);
  const steps = (state?.steps ?? []).map((s) => ({
    id: s.id, jobId: s.job_id, sessionId: s.session_id, repo: s.repo, number: s.number, title: s.title, phase: s.phase,
    phaseSince: s.phase_since, blockedBy: s.blocked_by,
  }));
  const stepsOf = (job: JobData | null) => (job ? steps.filter((s) => s.jobId === job.id) : []);
  const details: Record<string, StepDetailData> = Object.fromEntries(
    Object.entries(state?.step_details ?? {}).map(([id, d]) => [id, {
      phaseEvents: d.phase_events, tests: d.tests, files: d.files, commits: d.commits, pr: d.pr, review: d.review,
      checklist: d.checklist, struggle: d.struggle && { failures: d.struggle.failures, churn: d.struggle.churn, silentForS: d.struggle.silent_for_s },
    }]),
  );
  const ticketStepOf = (job: JobData | null) => {
    const [step] = stepsOf(job);
    return step ? { step, detail: details[step.id] ?? null } : null;
  };
  const flow = flowRows(repos?.map((r) => r.repo) ?? [], view.shown, jobs, steps).map((r) => ({
    repo: r.repo,
    chips: r.chips.map(({ sessionId, stepId, ...c }) => ({
      ...c, selected: sessionId === selectedId && (!stepId || !selectedStepId || stepId === selectedStepId),
      onOpen: () => open(sessionId, stepId),
    })),
  }));
  const plans: WayfinderData[] = (state?.wayfinder ?? []).map((w) => ({
    sessionId: w.session_id, map: w.map, ticket: w.ticket, questions: w.questions, created: w.created, closed: w.closed,
  }));
  const maps: MapData[] = (state?.maps ?? []).map((m) => ({
    repo: m.repo, number: m.number, title: m.title, url: m.url, destination: m.destination, fog: m.fog,
    tickets: m.tickets.map((t): DecisionTicketData => ({
      number: t.number, title: t.title, url: t.url, state: t.state, type: t.type, mode: t.mode, assignees: t.assignees,
      gist: t.gist, blockedBy: t.blocked_by,
    })),
  }));
  const research: ResearchData[] = (state?.research ?? []).map((r) => ({
    sessionId: r.session_id, question: r.question, searches: r.searches, sources: r.sources, findings: r.findings,
  }));
  const toSpecs: ToSpecData[] = (state?.to_spec ?? []).map((t) => ({ sessionId: t.session_id, map: t.map, spec: t.spec, outline: t.outline }));
  const toTickets: ToTicketsData[] = (state?.to_tickets ?? []).map((t) => ({
    sessionId: t.session_id, spec: t.spec,
    tickets: t.tickets.map((x) => ({ number: x.number, title: x.title, url: x.url, state: x.state, blockedBy: x.blocked_by })),
  }));
  /** A Work item by number in the session's repo, named as last polled (by number alone before that). */
  const itemRef = (repo: string, n: number | null | undefined) => {
    if (n == null) return null;
    const w = state?.work_items.find((x) => x.repo === repo && x.number === n);
    return w ? { name: `#${n} ${w.title}`, url: w.url } : { name: `#${n}`, url: `https://github.com/${repo}/issues/${n}` };
  };
  const planOf = (sessionId: string) => plans.find((p) => p.sessionId === sessionId) ?? null;
  const mapOf = (s: { id: string; repo: string }) => {
    const n = planOf(s.id)?.map;
    return maps.find((m) => m.repo === s.repo && m.number === n) ?? null;
  };
  const toSpecOf = (sessionId: string) => toSpecs.find((t) => t.sessionId === sessionId) ?? null;
  const toTicketsOf = (sessionId: string) => toTickets.find((t) => t.sessionId === sessionId) ?? null;
  /** What a session of each planning kind works on; any other session, its Job's Work item. */
  const workItemByKind: Record<string, (s: Session) => { name: string; url: string } | null> = {
    [WAYFINDER]: (s) => {
      const m = mapOf(s);
      return m && { name: `#${m.number} ${m.title}`, url: m.url };
    },
    [TO_SPEC]: (s) => itemRef(s.repo, toSpecOf(s.id)?.spec ?? toSpecOf(s.id)?.map),
    [TO_TICKETS]: (s) => itemRef(s.repo, toTicketsOf(s.id)?.spec),
  };
  const workItemOf = (s: Session) => workItemByKind[s.kind]?.(s) ?? jobOf(s.id)?.workItem ?? null;
  const abandonJobOf = (s: Session) => () => {
    const j = jobOf(s.id);
    if (j) abandon(j.id);
  };
  /** Each session kind's detail view; kinds without their own view yet show the ad hoc view, titled by their kind. */
  const detailByKind: Record<string, (s: Session) => ReactNode> = {
    [TICKET_JOB]: (s) => (
      <TicketJobView {...s} job={jobOf(s.id)} step={ticketStepOf(jobOf(s.id))} nowMs={now} onAbandon={abandonJobOf(s)} />
    ),
    [SPEC_JOB]: (s) => (
      <SpecJobView
        key={s.id}
        {...s}
        job={jobOf(s.id)}
        steps={stepsOf(jobOf(s.id))}
        details={details}
        review={state?.job_reviews[jobOf(s.id)?.id ?? ""] ?? null}
        nowMs={now}
        onAbandon={abandonJobOf(s)}
        stepId={selectedStepId}
        onSelectStep={setSelectedStepId}
      />
    ),
    [WAYFINDER]: (s) => <WayfinderView key={s.id} {...s} plan={planOf(s.id)} map={mapOf(s)} />,
    [RESEARCH]: (s) => <ResearchView key={s.id} {...s} research={research.find((r) => r.sessionId === s.id) ?? null} />,
    [TO_SPEC]: (s) => (
      <ToSpecView key={s.id} {...s} toSpec={toSpecOf(s.id)} map={itemRef(s.repo, toSpecOf(s.id)?.map)} spec={itemRef(s.repo, toSpecOf(s.id)?.spec)} />
    ),
    [TO_TICKETS]: (s) => <ToTicketsView key={s.id} {...s} toTickets={toTicketsOf(s.id)} spec={itemRef(s.repo, toTicketsOf(s.id)?.spec)} />,
  };
  const detailOf = (s: Session) => detailByKind[s.kind]?.(s) ?? <AdHocView {...s} />;

  const seen = (id: string) => void fetch(`/api/sessions/${id}/seen`, { method: "POST" }).catch(() => {});
  /** Opening a session's detail, from its row, its inbox card or a flow-strip chip (with that chip's Step open),
   * makes its Done seen. */
  const open = (id: string, stepId?: string) => {
    setSelectedId(id);
    setSelectedStepId(stepId);
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
          <HistoryCount count={history.length} open={showHistory} onToggle={() => { setShowHistory(!showHistory); setReplayId(undefined); }} />
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
                  workItem={workItemOf(s)}
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
                  workItem={workItemOf(s)}
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
        {showHistory ? (
          replayJob ? (
            <ReplayView key={replayJob.id} job={replayJob} replay={replay?.job_id === replayJob.id ? replay : null} onBack={() => setReplayId(undefined)} />
          ) : <HistoryList jobs={history} onReplay={setReplayId} />
        ) : null}
        {repos ? <FlowStrip rows={flow} /> : null}
        {state ? (
          <SessionTable
            sessions={showHiddenSessions ? [...view.shown, ...view.hiddenSessions] : view.shown}
            selectedId={selectedId}
            onSelect={(id) => open(id)}
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
        {selected ? detailOf(selected) : null}
      </Split>
    </>
  );
}
