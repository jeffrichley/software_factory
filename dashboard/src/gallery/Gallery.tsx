import { useEffect, useState, type ReactNode } from "react";
import {
  AdHocView,
  AD_HOC,
  DoneCard,
  DoneUnseenCount,
  HiddenNeedsBadge,
  HistoryCount,
  HistoryList,
  NeedsCount,
  Tag,
  Empty,
  Eyebrow,
  FlowStrip,
  GraphView,
  Icon,
  Inbox,
  InboxHeader,
  MachinePill,
  MachinePills,
  NeedsYouCard,
  NowLine,
  Panel,
  PHASES,
  PhaseName,
  PhaseTrack,
  ReplayView,
  ResearchView,
  SectionHeading,
  SoundToggle,
  SpecJobView,
  StepDetail,
  ToSpecView,
  ToTicketsView,
  WayfinderView,
  SessionHeader,
  HiddenSessions,
  NeedsDetail,
  Split,
  TicketJobView,
  TopBar,
  StateBadge,
  StateChip,
  StaleNote,
  StateDot,
  Unknown,
  UnknownPhase,
  UnknownPhaseTag,
  type Phase,
  type SessionState,
  type StateChipProps,
} from "../ds";
import {
  adhocActions, flowRows, freshStep, MAP, mapItems, mapFog, needsCards, REPLAY, REPLAY_JOB, research, SPEC_JOB, specDetails, specItems,
  specSteps, ticketItems, ticketStep, toSpec, toTickets, wayfinderPlan,
} from "./fixtures";
import "./gallery.css";

type Theme = "system" | "light" | "dark";

function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const fromUrl = new URLSearchParams(location.search).get("theme");
    if (fromUrl === "light" || fromUrl === "dark" || fromUrl === "system") return fromUrl;
    try {
      return (localStorage.getItem("factory-theme") as Theme) || "system";
    } catch {
      return "system";
    }
  });
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("factory-theme", theme);
    } catch {
      /* per-viewer convenience only */
    }
  }, [theme]);
  return [theme, setTheme];
}

function Section({ id, title, note, children }: { id: string; title: string; note?: string; children: ReactNode }) {
  return (
    <section className="g-section" id={id} aria-labelledby={`${id}-h`}>
      <header className="g-section-h">
        <h2 id={`${id}-h`}>{title}</h2>
        {note ? <p>{note}</p> : null}
      </header>
      {children}
    </section>
  );
}

function Specimen({ label, children }: { label: string; children: ReactNode }) {
  return (
    <figure className="g-spec">
      <div className="g-spec-b">{children}</div>
      <figcaption>{label}</figcaption>
    </figure>
  );
}

const SWATCHES: [string, string[]][] = [
  ["Surfaces", ["--bg", "--surface-sunken", "--surface", "--surface-2", "--surface-3", "--line", "--line-2", "--line-hover"]],
  ["Text", ["--text-strong", "--text", "--text-2", "--text-3"]],
  ["Needs you (amber)", ["--needs", "--needs-hover", "--needs-ink", "--needs-fg", "--needs-bg", "--needs-line", "--needs-text", "--needs-soft", "--needs-label"]],
  ["Working (blue)", ["--working", "--working-bg", "--working-line"]],
  ["Done (teal)", ["--done", "--done-bg", "--done-line"]],
  ["Stale (grey, dashed)", ["--stale", "--stale-bg"]],
  ["Tests & graph", ["--pass", "--fail", "--fail-soft", "--fail-bg", "--fail-line", "--edge-resolved", "--edge-waiting", "--fog"]],
];
const TYPE: [string, string, string, string][] = [
  ["--fs-3xl", "64", "--font-mono", "mono 700 — inbox count"],
  ["--fs-2xl", "40", "--font-display", "display"],
  ["--fs-xl", "28", "--font-display", "display 600 — detail title, inbox heading"],
  ["--fs-lg", "20", "--font-display", "display 600 — Step title"],
  ["--fs-md", "16", "--font-body", "body — default"],
  ["--fs-sm", "14", "--font-body", "body — meta, cards"],
  ["--fs-xs", "12", "--font-mono", "mono — eyebrow, chips"],
  ["--fs-2xs", "11", "--font-mono", "mono — tags, column heads"],
];
const SPACE = ["--s1", "--s2", "--s3", "--s4", "--s5", "--s6", "--s7"];
const RADII = ["--r-xs", "--r-sm", "--r", "--r-lg", "--r-pill"];

const headerStates: [SessionState, boolean][] = [["Working", false], ["Needs you", false], ["Done", false], ["Done", true], ["Stale", false]];

const chip = (over: Partial<StateChipProps> & Pick<StateChipProps, "id">): StateChipProps => ({
  label: "Spec DAG view",
  name: "Spec Job: Steps and the Ticket DAG",
  state: "Working",
  phase: "Green",
  machine: "mac-studio",
  repo: "software_factory",
  ...over,
});

export function Gallery() {
  const [theme, setTheme] = useTheme();
  const [glidePhase, setGlidePhase] = useState(2);
  const [hidden, setHidden] = useState<Set<string>>(new Set(["win-ps"]));
  const [selected, setSelected] = useState<string | undefined>("api");
  const [mapSel, setMapSel] = useState<string | undefined>();
  const [hiddenListOpen, setHiddenListOpen] = useState(true);
  const [mapFit, setMapFit] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [soundOn, setSoundOn] = useState(true);
  const [selectedSpecStep, setSelectedSpecStep] = useState<string | undefined>("s28");
  const toggle = (m: string) => setHidden((h) => { const n = new Set(h); if (n.has(m)) n.delete(m); else n.add(m); return n; });
  const glideRows = flowRows.map((r, i) =>
    i === 0 ? { ...r, chips: r.chips.map((c) => (c.id === "glide" ? { ...c, phase: PHASES[glidePhase] as Phase } : c)) } : r,
  );

  return (
    <div className="g">
      <header className="g-top">
        <div className="g-brand"><span className="g-mark" aria-hidden="true" />Factory <small>design system</small></div>
        <nav className="g-nav" aria-label="Sections">
          {["tokens", "states", "topbar", "detail", "step", "spec", "planning", "machines", "history", "replay", "chips", "flow", "inbox", "panels", "phase", "graph", "unknown"].map((s) => <a key={s} href={`#${s}`}>{s}</a>)}
        </nav>
        <div className="g-theme" role="group" aria-label="Theme">
          {(["system", "light", "dark"] as const).map((t) => (
            <button key={t} type="button" className={`btn${theme === t ? " btn-on" : ""}`} aria-pressed={theme === t} onClick={() => setTheme(t)}>{t}</button>
          ))}
        </div>
      </header>

      <main className="g-main">
        <p className="g-lede">
          Every dashboard widget, in every state, with fake data. Built from prototype variant E (branch <code className="mono">prototype/dashboard</code>, <code className="mono">?variant=E</code>). The dashboard uses only these tokens and components.
        </p>

        <Section id="tokens" title="Tokens" note="Colour roles switch with the theme; everything else is shared.">
          {SWATCHES.map(([group, vars]) => (
            <div key={group} className="g-swatches">
              <Eyebrow>{group}</Eyebrow>
              <div className="g-swatch-row">
                {vars.map((v) => (
                  <div key={v} className="g-swatch"><span style={{ background: `var(${v})` }} /><code>{v}</code></div>
                ))}
              </div>
            </div>
          ))}
          <div className="g-grid2">
            <Panel title="Type scale · Plex Sans Condensed / Sans / Mono">
              {TYPE.map(([v, px, font, use]) => (
                <div key={v} className="g-type"><span style={{ fontSize: `var(${v})`, fontFamily: `var(${font})` }}>Aa {px}</span><code>{v}</code><span className="muted">{use}</span></div>
              ))}
              <div className="g-type"><span>Body copy reads like this.</span><code>--font-body</code></div>
              <div className="g-type"><span className="mono">ticket-20-design-system</span><code>--font-mono</code></div>
            </Panel>
            <div className="g-stack">
              <Panel title="Spacing">
                {SPACE.map((v) => <div key={v} className="g-space"><span style={{ width: `var(${v})` }} /><code>{v}</code></div>)}
              </Panel>
              <Panel title="Radii">
                <div className="g-row">{RADII.map((v) => <div key={v} className="g-radius"><span style={{ borderRadius: `var(${v})` }} /><code>{v}</code></div>)}</div>
              </Panel>
              <Panel title="Motion">
                <div className="g-row">
                  <span className="g-motion"><span className="dot dot-needs pulse" /> pulse <code>--dur-pulse</code></span>
                  <span className="g-motion"><span className="g-flash fchip fs-needs"><span className="fl">flash</span></span><code>--dur-flash</code></span>
                  <span className="g-motion">glide <code>--dur-glide</code></span>
                  <span className="g-motion">hover <code>--dur</code> <code>--ease-out</code></span>
                </div>
                <p className="muted g-small">All motion stops under prefers-reduced-motion.</p>
              </Panel>
            </div>
          </div>
        </Section>

        <Section id="states" title="State badge & dot" note="Working blue · Needs you amber · Done teal (unseen bright, seen quiet) · Stale grey dashed.">
          <div className="g-row">
            <StateBadge state="Needs you" />
            <StateBadge state="Working" />
            <StateBadge state="Done" />
            <StateBadge state="Done" seen />
            <StateBadge state="Stale" />
          </div>
          <div className="g-row">
            <StateDot state="Needs you" /> <StateDot state="Working" /> <StateDot state="Done" /> <StateDot state="Done" seen /> <StateDot state="Stale" />
          </div>
        </Section>

        <Section id="topbar" title="Top bar" note="Machine pills and the header's counts. There is no session table (as in variant E): sessions are reached through the flow strip, the inbox and the default selection.">
          <TopBar>
            <MachinePills>
              <MachinePill name="mac-studio" sessions={5} />
              <MachinePill name="wsl-desk" sessions={3} />
              <MachinePill name="mbp-travel" sessions={2} silentForMs={14 * 60_000} />
            </MachinePills>
          </TopBar>
        </Section>

        <Section id="detail" title="Session detail (ad hoc)" note="AdHocView: header with state, time in state and the now: headline; a timeline of the last actions, the latest marked. Other kinds use it, titled by their kind, until their own view arrives.">
          <AdHocView machine="desk-wsl" repo="worlds" kind={AD_HOC} state="Working" inStateMs={4 * 60_000} now="reading src/render/chunk.ts" unknownSkill={null} actions={adhocActions} />
          <AdHocView machine="mac-mini" repo="gateway" kind={AD_HOC} state="Done" inStateMs={30_000} now={null} unknownSkill="deploy-preview" actions={[]} />
          <Eyebrow>Needs you · the centre's Needs you block, and the Hide button beside the crumbs</Eyebrow>
          <AdHocView
            machine="wsl-desk" repo="jeff/widgets" kind="Ticket Job" state="Needs you" inStateMs={3 * 60_000} now="started `implement`" unknownSkill={null} actions={adhocActions.slice(-3)}
            needs={{ reason: { kind: "permission", tool: "Bash", command: "rm -rf .factory/tmp && npm test" }, session: "0196viHB", terminal: null, resumeCommand: "claude --resume 0196viHB-5c2e", onCopy: () => {} }}
            controls={<button type="button" className="btn"><Icon name="eye-off" />Hide this session</button>}
          />
          <Eyebrow>Stale · its Machine silent, with when it was last seen</Eyebrow>
          <AdHocView machine="mbp-travel" repo="worlds" kind={AD_HOC} state="Stale" staleReason="Machine silent" machineSilentForMs={31 * 60_000} inStateMs={31 * 60_000} now="running cargo build" unknownSkill={null} actions={adhocActions.slice(-2)} />
          <Eyebrow>Needs you block · every reason</Eyebrow>
          <NeedsDetail reason={{ kind: "question", text: "Which of the three layouts should win?" }} waitingMs={60_000} machine="desk-win" session="wf" terminal={null} resumeCommand="claude --resume wf" />
          <NeedsDetail reason={{ kind: "hitl", ticket: "#53 Prototype the dashboard", questions: ["Q1 - Layout", "Q2 - Flow strip"] }} waitingMs={34 * 60_000} machine="desk-win" session="wf" terminal="tmux · factory:2" resumeCommand="claude --resume wf" />
          <NeedsDetail reason={null} waitingMs={5_000} machine="desk-win" session="7f3e21c0" terminal={null} resumeCommand="claude --resume 7f3e21c0" />
          <Eyebrow>Ticket Job · PR open, Done</Eyebrow>
          <TicketJobView
            machine="wsl-desk" repo="jeff/widgets" kind="Ticket Job" state="Done" inStateMs={2 * 60_000} now="ran `factory report pr`" actions={adhocActions.slice(-2)}
            onAbandon={() => {}}
            job={{ id: "12", sessionId: "3", machine: "wsl", kind: "Ticket Job", repo: "jeff/widgets", startedAt: "2026-10-26T12:00:00Z", duplicateOf: null, number: 28, workItem: { name: "Ticket Job: launch to Done", url: "https://github.com/jeff/widgets/issues/28" }, stage: "PR open", branch: "worktree-ticket-28-ticket-job-launch-to-done", worktree: "/home/jeff/widgets/.claude/worktrees/ticket-28-ticket-job-launch-to-done", pr: { number: 46, url: "https://github.com/jeff/widgets/pull/46", draft: false } }}
          />
          <Eyebrow>Ticket Job · Step detail: struggling, PR with CI checks</Eyebrow>
          <TicketJobView
            machine="wsl-desk" repo="jeff/widgets" kind="Ticket Job" state="Working" inStateMs={23 * 60_000} now="running uv run pytest" actions={adhocActions.slice(-2)}
            step={ticketStep}
            job={{ id: "16", sessionId: "7", machine: "wsl-desk", kind: "Ticket Job", repo: "jeff/widgets", startedAt: "2026-10-26T12:00:00Z", duplicateOf: null, number: 31, workItem: { name: "Ticket Job Step detail", url: "https://github.com/jeff/widgets/issues/31" }, stage: "PR open", branch: "ticket-31-step-detail", worktree: null, pr: { number: 52, url: "https://github.com/jeff/widgets/pull/52", draft: false } }}
          />
          <Eyebrow>Ticket Job · Step just started, silent, no checklist</Eyebrow>
          <TicketJobView
            machine="mac-studio" repo="jeff/widgets" kind="Ticket Job" state="Working" inStateMs={12 * 60_000} now={null} actions={[]}
            step={freshStep}
            job={{ id: "17", sessionId: "8", machine: "mac-studio", kind: "Ticket Job", repo: "jeff/widgets", startedAt: "2026-10-26T12:00:00Z", duplicateOf: null, number: 33, workItem: null, stage: "In progress", branch: null, worktree: null, pr: null }}
          />
          <Eyebrow>Ticket Job · Work item unknown, ended without a PR</Eyebrow>
          <TicketJobView
            machine="mac-studio" repo="jeff/widgets" kind="Ticket Job" state="Needs you" inStateMs={60_000} now={null} actions={[]}
            job={{ id: "13", sessionId: "4", machine: "wsl", kind: "Ticket Job", repo: "jeff/widgets", startedAt: "2026-10-26T12:00:00Z", duplicateOf: null, number: null, workItem: null, stage: "In progress", branch: null, worktree: null, pr: null }}
          />
          <Eyebrow>Ticket Job · draft PR</Eyebrow>
          <TicketJobView
            machine="wsl-desk" repo="jeff/widgets" kind="Ticket Job" state="Working" inStateMs={30_000} now="pushing" actions={[]}
            job={{ id: "14", sessionId: "5", machine: "wsl", kind: "Ticket Job", repo: "jeff/widgets", startedAt: "2026-10-26T12:00:00Z", duplicateOf: null, number: 31, workItem: null, stage: "In progress", branch: null, worktree: "/home/jeff/widgets-31", pr: { number: 47, url: "https://github.com/jeff/widgets/pull/47", draft: true } }}
          />
          <Eyebrow>Ticket Job · duplicate, can be marked abandoned</Eyebrow>
          <TicketJobView
            machine="mac-studio" repo="jeff/widgets" kind="Ticket Job" state="Working" inStateMs={90_000} now="reading src/api.ts" actions={[]} onAbandon={() => {}}
            job={{ id: "15", sessionId: "6", machine: "wsl", kind: "Ticket Job", repo: "jeff/widgets", startedAt: "2026-10-26T12:00:00Z", duplicateOf: "12", number: 28, workItem: { name: "Ticket Job: launch to Done", url: "https://github.com/jeff/widgets/issues/28" }, stage: "In progress", branch: null, worktree: null, pr: null }}
          />
          <Eyebrow>Session header · every state</Eyebrow>
          {headerStates.map(([state, seen]) => (
            <SessionHeader key={`${state}-${seen}`} machine="mac-studio" repo="jeff/widgets" kind="research" state={state} seen={seen} staleReason={state === "Stale" ? "Machine silent" : undefined} inStateMs={7 * 60_000} now={state === "Stale" ? null : "fetching https://docs.github.com/rest"} title="research session" />
          ))}
          <SessionHeader machine="wsl-desk" repo="jeff/gadgets" kind="ad hoc" state="Working" quietMs={23 * 60_000} inStateMs={41 * 60_000} now="running uv run pytest" title="Working · quiet (no events for 23m)" />
        </Section>

        <Section id="step" title="Step detail" note="StepDetail on its own: a Step's Phase track and time in Phase, test pulse, files with edits and +/− lines (one unknown), commits, PR with checks, review findings, the agent's checklist and the struggle badge; in a Spec Job, Blocked by and no PR of its own.">
          <Eyebrow>Ticket Job Step · struggling, every part known</Eyebrow>
          <StepDetail step={ticketStep.step} detail={ticketStep.detail} nowMs={Date.now()} />
          <Eyebrow>Spec Job Step · blocked, Phase unknown, no detail yet</Eyebrow>
          <StepDetail step={{ number: 31, title: "Step detail", phase: null, phaseSince: new Date().toISOString() }} detail={null} nowMs={Date.now()} inSpecJob blockers={["#28 Ticket Job: launch to Done"]} />
          <Eyebrow>Step just started · silent, no checklist, Ticket title unknown</Eyebrow>
          <StepDetail step={freshStep.step} detail={freshStep.detail} nowMs={Date.now()} />
        </Section>

        <Section id="spec" title="Spec Job detail" note="SpecJobView: Spec, stage, integration branch, merged count, PR and whole-branch review; the Ticket DAG; the Step opened from the DAG (or from its flow-strip chip). Click a node to open its Step.">
          <Eyebrow>Spec Job · a Step open, draft PR</Eyebrow>
          <SpecJobView
            machine="wsl-desk" repo="jeff/widgets" kind="Spec Job" state="Working" inStateMs={9 * 60_000} now="running uv run pytest" actions={adhocActions.slice(-3)}
            job={SPEC_JOB} steps={specSteps} details={specDetails} review={{ standards: 3, spec: 0, source: "summary" }} nowMs={Date.now()} onAbandon={() => {}}
            stepId={selectedSpecStep} onSelectStep={setSelectedSpecStep}
          />
          <Eyebrow>Spec Job · no Step open</Eyebrow>
          <SpecJobView
            machine="wsl-desk" repo="jeff/widgets" kind="Spec Job" state="Needs you" inStateMs={60_000} now={null} actions={[]}
            job={{ ...SPEC_JOB, duplicateOf: "29", pr: null }} steps={specSteps} nowMs={Date.now()}
          />
          <Eyebrow>Spec Job · no Tickets read yet, Spec unknown</Eyebrow>
          <SpecJobView
            machine="mac-studio" repo="jeff/widgets" kind="Spec Job" state="Working" inStateMs={20_000} now="started `implement-spec`" actions={[]}
            job={{ ...SPEC_JOB, number: null, workItem: null, branch: null, worktree: null, pr: null }} steps={[]} nowMs={Date.now()}
          />
        </Section>

        <Section id="planning" title="Planning views" note="Wayfinder, research, to-spec and to-tickets sessions: the plan taking shape, each in every state, and unknown until the server has seen it start.">
          <Eyebrow>Wayfinder · grilling a HITL Decision ticket, waiting on the human</Eyebrow>
          <WayfinderView machine="wsl-desk" repo="jeff/widgets" kind="Wayfinder" state="Needs you" inStateMs={4 * 60_000} now={null} actions={adhocActions.slice(-2)} plan={wayfinderPlan} map={MAP}
            needs={{ reason: { kind: "hitl", ticket: "#53 Prototype the dashboard", questions: ["Q1 - Layout"] }, session: "wf", terminal: null, resumeCommand: "claude --resume wf" }} />
          <Eyebrow>Wayfinder · Map unknown</Eyebrow>
          <WayfinderView machine="mac-studio" repo="jeff/widgets" kind="Wayfinder" state="Working" inStateMs={30_000} now="started `wayfinder`" actions={[]} plan={null} map={null} />
          <Eyebrow>research · findings written</Eyebrow>
          <ResearchView machine="mac-studio" repo="jeff/widgets" kind="research" state="Done" inStateMs={2 * 60_000} now={null} actions={adhocActions.slice(-2)} research={research} />
          <Eyebrow>research · just started</Eyebrow>
          <ResearchView machine="mac-studio" repo="jeff/widgets" kind="research" state="Working" inStateMs={10_000} now={null} actions={[]} research={null} />
          <Eyebrow>to-spec · outline part-written</Eyebrow>
          <ToSpecView machine="wsl-desk" repo="jeff/widgets" kind="to-spec" state="Working" inStateMs={3 * 60_000} now="writing the spec" actions={[]} toSpec={toSpec} map={{ name: "#1 Widget export", url: MAP.url }} spec={null} />
          <Eyebrow>to-spec · just started</Eyebrow>
          <ToSpecView machine="wsl-desk" repo="jeff/widgets" kind="to-spec" state="Working" inStateMs={10_000} now={null} actions={[]} toSpec={null} map={null} spec={null} />
          <Eyebrow>to-tickets · Tickets created</Eyebrow>
          <ToTicketsView machine="wsl-desk" repo="jeff/widgets" kind="to-tickets" state="Done" inStateMs={60_000} now={null} actions={[]} toTickets={toTickets} spec={{ name: "#18 The Factory", url: SPEC_JOB.workItem?.url ?? "#" }} />
          <Eyebrow>to-tickets · just started</Eyebrow>
          <ToTicketsView machine="wsl-desk" repo="jeff/widgets" kind="to-tickets" state="Working" inStateMs={10_000} now={null} actions={[]} toTickets={null} spec={null} />
        </Section>

        <Section id="machines" title="Machine pills & header counts" note="Click a pill to toggle it; hidden Machines still count their Needs you.">
          <MachinePills>
            <MachinePill name="mac-studio" sessions={5} hidden={hidden.has("mac-studio")} onToggle={() => toggle("mac-studio")} />
            <MachinePill name="wsl-desk" sessions={3} hidden={hidden.has("wsl-desk")} onToggle={() => toggle("wsl-desk")} />
            <MachinePill name="win-ps" sessions={1} hidden={hidden.has("win-ps")} onToggle={() => toggle("win-ps")} />
            <MachinePill name="mbp-travel" sessions={2} silentForMs={14 * 60_000} hidden={hidden.has("mbp-travel")} onToggle={() => toggle("mbp-travel")} />
          </MachinePills>
          <div className="g-row">
            <NeedsCount count={3} />
            <NeedsCount count={0} />
            <HiddenNeedsBadge count={1} onShow={() => setHidden(new Set())} />
            <DoneUnseenCount count={2} />
            <SoundToggle on={soundOn} onToggle={() => setSoundOn(!soundOn)} />
            <SoundToggle on={false} onToggle={() => {}} />
          </div>
        </Section>

        <Section id="history" title="History" note="Merged, Closed and Abandoned Jobs, latest first, with their outcome. The header button opens it.">
          <div className="g-row">
            <HistoryCount count={3} open={historyOpen} onToggle={() => setHistoryOpen(!historyOpen)} />
            <HistoryCount count={0} open={false} onToggle={() => {}} />
          </div>
          <HistoryList
            onReplay={() => {}}
            jobs={[
              { id: "21", sessionId: "7", machine: "wsl", kind: "Ticket Job", repo: "jeff/widgets", startedAt: "2026-10-26T15:30:00Z", duplicateOf: null, number: 29, workItem: { name: "Job edges, abandonment and the History list", url: "https://github.com/jeff/widgets/issues/29" }, stage: "Merged", branch: null, worktree: "/home/jeff/widgets/.claude/worktrees/ticket-29-job-edges", pr: { number: 48, url: "https://github.com/jeff/widgets/pull/48", draft: false } },
              { id: "17", sessionId: "6", machine: "wsl", kind: "Ticket Job", repo: "jeff/gadgets", startedAt: "2026-10-26T13:05:00Z", duplicateOf: null, number: 7, workItem: null, stage: "Closed", branch: null, worktree: null, pr: { number: 9, url: "https://github.com/jeff/gadgets/pull/9", draft: false } },
              { id: "15", sessionId: "6", machine: "wsl", kind: "Ticket Job", repo: "jeff/widgets", startedAt: "2026-10-26T12:00:00Z", duplicateOf: "12", number: null, workItem: null, stage: "Abandoned", branch: null, worktree: null, pr: null },
            ]}
          />
          <HistoryList jobs={[]} />
        </Section>

        <Section id="replay" title="Replay" note="A finished Job over time: play/pause, the scrubber with its events marked, each Step's Phase at that moment, and every event. Click a marker or an event to jump to it.">
          <ReplayView job={REPLAY_JOB} replay={REPLAY} onBack={() => {}} initialPos={200} />
          <ReplayView job={REPLAY_JOB} replay={null} onBack={() => {}} />
        </Section>

        <Section id="chips" title="State chips" note="Hover or focus for the tooltip. Red/Green Phases underline; unknown Phase is dotted; long names ellipsize.">
          <div className="g-chips">
            <Specimen label="Needs you (pulse + flash)"><StateChip {...chip({ id: "c1", state: "Needs you", phase: "Red" })} /></Specimen>
            <Specimen label="Working · Green"><StateChip {...chip({ id: "c2" })} /></Specimen>
            <Specimen label="Working · Red"><StateChip {...chip({ id: "c3", phase: "Red" })} /></Specimen>
            <Specimen label="Done · unseen"><StateChip {...chip({ id: "c4", state: "Done", phase: "Merged" })} /></Specimen>
            <Specimen label="Done · seen"><StateChip {...chip({ id: "c5", state: "Done", seen: true, phase: "Merged" })} /></Specimen>
            <Specimen label="Stale"><StateChip {...chip({ id: "c6", state: "Stale", staleReason: "Machine silent", phase: "Refactor" })} /></Specimen>
            <Specimen label="Working · quiet (dimmed)"><StateChip {...chip({ id: "c6q", quietMs: 23 * 60_000, phase: "Green" })} /></Specimen>
            <Specimen label="Phase unknown"><StateChip {...chip({ id: "c7", phase: null, label: "Worktree cleanup" })} /></Specimen>
            <Specimen label="Spec Step (group initials)"><StateChip {...chip({ id: "c8", group: "TF", groupName: "Spec Job · The Factory", blocked: true, phase: "Exploring" })} /></Specimen>
            <Specimen label="Planning (Wayfinder)"><StateChip {...chip({ id: "c9", phase: "planning", label: "Wayfinder", planIcon: "flag", groupName: "Wayfinder" })} /></Specimen>
            <Specimen label="Research"><StateChip {...chip({ id: "c10", phase: "planning", label: "research", planIcon: "search", groupName: "research", state: "Done" })} /></Specimen>
            <Specimen label="Selected"><StateChip {...chip({ id: "c11", selected: true })} /></Specimen>
            <Specimen label="Selected · Needs you"><StateChip {...chip({ id: "c12", selected: true, state: "Needs you" })} /></Specimen>
            <Specimen label="Long name in a narrow cell">
              <div className="fcell g-narrow"><StateChip {...chip({ id: "c13", label: "Install, uninstall and status for real across every Machine" })} /></div>
            </Specimen>
          </div>
        </Section>

        <Section id="flow" title="Flow strip" note="One row per Tracked repo. The crowded cell wraps to two lines and clips; it never overflows. Advance the glide chip to watch it move.">
          <div className="g-row">
            <button type="button" className="btn" onClick={() => setGlidePhase((p) => (p + 1) % PHASES.length)}>
              <Icon name="arrow" />Advance glide chip (now {PHASES[glidePhase]})
            </button>
          </div>
          <div className="g-bleed"><FlowStrip rows={glideRows} /></div>
        </Section>

        <Section id="inbox" title="Needs you inbox" note="Every reason; then Done-unseen.">
          <div className="g-inbox">
            <div className="g-inbox-col">
              <InboxHeader count={needsCards.length} />
              {needsCards.map((c, i) => <NeedsYouCard key={i} {...c} waitingMs={c.waitingMs} selected={i === 0} onCopy={(t) => navigator.clipboard?.writeText(t).catch(() => {})} />)}
            </div>
            <div className="g-inbox-col">
              <InboxHeader count={0} />
              <Empty><Icon name="check" /> Nothing needs you. New questions and permission prompts land here.</Empty>
              <SectionHeading icon="check" tone="done">Done — unseen · 2</SectionHeading>
              <DoneCard kind="Ticket Job" workItem={{ name: "#24 Needs you and Done sounds", url: "#" }} repo="software_factory" machine="wsl-desk" agoMs={6 * 60_000} now="opened PR #41 — ready for review" />
              <DoneCard kind="ad hoc" workItem={null} repo="gateway" machine="mac-studio" agoMs={41 * 60_000} now={null} />
              <SectionHeading icon="check" tone="done">Done — unseen · 0</SectionHeading>
              <Empty>Everything Done has been seen.</Empty>
              <HiddenSessions
                sessions={[{ id: "h1", kind: "ad hoc", repo: "jeff/widgets", machine: "wsl-desk" }, { id: "h2", kind: "research", repo: "jeff/gadgets", machine: "mac-studio" }]}
                open={hiddenListOpen} onToggle={() => setHiddenListOpen(!hiddenListOpen)} selectedId="h2" onOpen={() => {}}
              />
            </div>
          </div>
          <TopBar>
            <MachinePills>
              <MachinePill name="wsl-desk" sessions={1} />
              <MachinePill name="mac-studio" sessions={2} silentForMs={9 * 60_000} />
            </MachinePills>
          </TopBar>
          <div className="g-split">
          <Split
            top={<FlowStrip rows={flowRows} />}
            side={
              <Inbox>
                <InboxHeader count={2} />
                <NeedsYouCard reason={{ kind: "permission", tool: "Bash", command: "git push" }} waitingMs={12_000} repo="jeff/widgets" kind={null} workItem={null} machine="wsl-desk" session="0196viHB" terminal={null} resumeCommand="claude --resume 0196viHB" />
                <NeedsYouCard reason={null} waitingMs={50_000} repo="jeff/widgets" kind={null} workItem={null} machine="mac-studio" session="7f3e21c0" terminal={null} resumeCommand="claude --resume 7f3e21c0" />
                <SectionHeading icon="check" tone="done">Done — unseen · 1</SectionHeading>
                <DoneCard kind={null} workItem={null} repo="jeff/gadgets" machine="mac-studio" agoMs={3 * 60_000} now={null} />
              </Inbox>
            }
          >
            <p className="muted g-small">The dashboard page: the top bar with its Machine pills, the flow strip full width, then the inbox on the left (kind and Work item unknown here) beside the centre, which shows one session's detail (or History, or a Replay) in place of a session table. On a wide screen the inbox and the centre each scroll on their own.</p>
          </Split>
          </div>
        </Section>

        <Section id="panels" title="Panel & section">
          <div className="g-grid2">
            <Panel title="Agent checklist (live)">
              <p className="muted g-small">Panels hold one block of a detail view: an uppercase mono title and content.</p>
            </Panel>
            <Panel title="Review findings">
              <Unknown />
            </Panel>
          </div>
          <SectionHeading icon="check" tone="done">Section heading · done tone</SectionHeading>
          <SectionHeading icon="alert" tone="needs">Section heading · needs tone</SectionHeading>
          <SectionHeading>Section heading · neutral</SectionHeading>
          <div className="g-row"><Tag>Ticket</Tag><Tag tone="frontier">Frontier</Tag><Tag tone="blocked">Blocked by #19</Tag><Tag tone="struggle"><Icon name="flame" />Struggling · 4 test failures</Tag><Tag tone="needs">Needs you</Tag><Tag tone="unknown">Phase unknown</Tag></div>
          <div className="g-row"><button type="button" className="btn">Default button</button><button type="button" className="btn btn-needs"><Icon name="copy" />Needs-you action</button><button type="button" className="btn btn-on">Toggled on</button></div>
          <NowLine now="running tests: uv run pytest tests/server" />
        </Section>

        <Section id="phase" title="Phase track" note="Seven Phases; past grey, current coloured (Red red, Green green, Merged teal, others blue).">
          <div className="g-stack">
            {PHASES.map((p) => (
              <div key={p} className="g-phase"><span className="g-phase-l"><PhaseName phase={p} /></span><PhaseTrack phase={p} /><div className="g-phase-c"><PhaseTrack phase={p} compact /></div></div>
            ))}
            <div className="g-phase"><span className="g-phase-l muted">unknown</span><PhaseTrack phase={null} /><div className="g-phase-c"><PhaseTrack phase={null} compact /></div></div>
          </div>
        </Section>

        <Section id="graph" title="Graph" note="One style for Spec DAGs, Maps and to-tickets output. Click a node to select it.">
          <Eyebrow>Spec Job · Ticket DAG (Steps)</Eyebrow>
          <GraphView label="Ticket DAG for The Factory" items={specItems} selectedId={selected} onSelect={setSelected} />
          <Eyebrow>Map · Decision tickets with fog past the frontier</Eyebrow>
          <GraphView label="Map: Software Factory" items={mapItems} fog={mapFog} selectedId={mapSel} onSelect={setMapSel} />
          <Eyebrow>Map · fitted to its box (Wayfinder's "Fit to width"); unfitted, a wide graph scrolls inside its box</Eyebrow>
          <div className="g-row"><button type="button" className="btn" aria-pressed={mapFit} onClick={() => setMapFit(!mapFit)}>{mapFit ? "Actual size" : "Fit to width"}</button></div>
          <div className="g-narrowbox"><GraphView label="Map: Software Factory, fitted" items={mapItems} fog={mapFog} legend={false} fit={mapFit} /></div>
          <Eyebrow>to-tickets output</Eyebrow>
          <GraphView label="Tickets created by to-tickets" items={ticketItems} legend={false} />
        </Section>

        <Section id="unknown" title="Unknown placeholders" note="Unknown data is shown as unknown, never guessed.">
          <div className="g-row"><span>Terminal: <Unknown /></span><UnknownPhaseTag /></div>
          <UnknownPhase detail="the Factory has received no Phase events for this Job, so there is no Phase track." />
          <StaleNote reason="Machine silent" machine="mbp-travel" silentForMs={14 * 60_000} />
          <StaleNote reason="Machine silent" />
        </Section>
      </main>
    </div>
  );
}
