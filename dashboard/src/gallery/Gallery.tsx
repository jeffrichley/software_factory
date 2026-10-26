import { useEffect, useState, type ReactNode } from "react";
import {
  DoneCard,
  DoneUnseenCount,
  HiddenNeedsBadge,
  NeedsCount,
  Tag,
  Empty,
  Eyebrow,
  FlowStrip,
  GraphView,
  Icon,
  InboxHeader,
  MachinePill,
  NeedsYouCard,
  NowLine,
  Panel,
  PHASES,
  PhaseName,
  PhaseTrack,
  SectionHeading,
  SessionTable,
  StateBadge,
  StateChip,
  StaleNote,
  StateDot,
  Unknown,
  UnknownPhase,
  UnknownPhaseTag,
  type Phase,
  type StateChipProps,
} from "../ds";
import { flowRows, mapItems, mapFog, needsCards, specItems, ticketItems } from "./fixtures";
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
  const toggle = (m: string) => setHidden((h) => { const n = new Set(h); if (n.has(m)) n.delete(m); else n.add(m); return n; });
  const glideRows = flowRows.map((r, i) =>
    i === 0 ? { ...r, chips: r.chips.map((c) => (c.id === "glide" ? { ...c, phase: PHASES[glidePhase] as Phase } : c)) } : r,
  );

  return (
    <div className="g">
      <header className="g-top">
        <div className="g-brand"><span className="g-mark" aria-hidden="true" />Factory <small>design system</small></div>
        <nav className="g-nav" aria-label="Sections">
          {["tokens", "states", "sessions", "machines", "chips", "flow", "inbox", "panels", "phase", "graph", "unknown"].map((s) => <a key={s} href={`#${s}`}>{s}</a>)}
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

        <Section id="sessions" title="Session table" note="One row per Tracked session; empty until a session starts in a Tracked repo.">
          <SessionTable
            sessions={[
              { id: "1", machine: "wsl-desk", repo: "jeff/widgets", state: "Working", inStateMs: 42_000 },
              { id: "2", machine: "mac-studio", repo: "jeff/a-much-longer-repository-name-that-ellipsizes", state: "Working", inStateMs: 2 * 3_600_000 + 14 * 60_000 },
            ]}
          />
          <SessionTable sessions={[]} />
        </Section>

        <Section id="machines" title="Machine pills & header counts" note="Click a pill to toggle it; hidden Machines still count their Needs you.">
          <div className="g-row">
            <MachinePill name="mac-studio" sessions={5} hidden={hidden.has("mac-studio")} onToggle={() => toggle("mac-studio")} />
            <MachinePill name="wsl-desk" sessions={3} hidden={hidden.has("wsl-desk")} onToggle={() => toggle("wsl-desk")} />
            <MachinePill name="win-ps" sessions={1} hidden={hidden.has("win-ps")} onToggle={() => toggle("win-ps")} />
            <MachinePill name="mbp-travel" sessions={2} silentForMs={14 * 60_000} hidden={hidden.has("mbp-travel")} onToggle={() => toggle("mbp-travel")} />
          </div>
          <div className="g-row">
            <NeedsCount count={3} />
            <NeedsCount count={0} />
            <HiddenNeedsBadge count={1} onShow={() => setHidden(new Set())} />
            <DoneUnseenCount count={2} />
          </div>
        </Section>

        <Section id="chips" title="State chips" note="Hover or focus for the tooltip. Red/Green Phases underline; unknown Phase is dotted; long names ellipsize.">
          <div className="g-chips">
            <Specimen label="Needs you (pulse + flash)"><StateChip {...chip({ id: "c1", state: "Needs you", phase: "Red" })} /></Specimen>
            <Specimen label="Working · Green"><StateChip {...chip({ id: "c2" })} /></Specimen>
            <Specimen label="Working · Red"><StateChip {...chip({ id: "c3", phase: "Red" })} /></Specimen>
            <Specimen label="Done · unseen"><StateChip {...chip({ id: "c4", state: "Done", phase: "Merged" })} /></Specimen>
            <Specimen label="Done · seen"><StateChip {...chip({ id: "c5", state: "Done", seen: true, phase: "Merged" })} /></Specimen>
            <Specimen label="Stale"><StateChip {...chip({ id: "c6", state: "Stale", staleReason: "Machine silent", phase: "Refactor" })} /></Specimen>
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
            </div>
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
          <Eyebrow>to-tickets output</Eyebrow>
          <GraphView label="Tickets created by to-tickets" items={ticketItems} legend={false} />
        </Section>

        <Section id="unknown" title="Unknown placeholders" note="Unknown data is shown as unknown, never guessed.">
          <div className="g-row"><span>Terminal: <Unknown /></span><UnknownPhaseTag /></div>
          <UnknownPhase detail="the Factory has received no Phase events for this Job, so there is no Phase track." />
          <StaleNote reason="Machine silent — mbp-travel last seen 14m ago" />
        </Section>
      </main>
    </div>
  );
}
