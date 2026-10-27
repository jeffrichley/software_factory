# Factory dashboard

React + TypeScript + Vite. Look and behaviour follow prototype variant E (branch `prototype/dashboard`, `?variant=E`).

```sh
npm install
npm run dev        # http://localhost:5173 — the dashboard (needs `factory server` on :47821); ?gallery for the design-system gallery (&theme=light|dark)
npm run build      # rebuilds dist/, which is committed: rebuild and commit it with every source change
npm run typecheck
npm test
```

## Design system (`src/ds`)

**Rule: the dashboard UI is built only from the design system's tokens and components. No one-off styling** — no raw colours, sizes, radii or timings, and no component-local CSS outside `src/ds`. Inside `src/ds`, colours, type, spacing, radii and motion come from `tokens.css`; a component's own fixed geometry (a 7px dot, an 18px badge) may stay literal in `components.css`. If a screen needs something the system lacks, add it to `src/ds` (token, component or variant), show it in the gallery in every state, and check it against variant E.

- `tokens.css` — colour roles written once as `light-dark(light, dark)` (dark = variant E, light derived; follows the OS unless `<html data-theme>` overrides), type scale, spacing, radii, motion. `motion.ts` mirrors the motion tokens for Framer Motion.
- Components: `MachinePill` (inert without `onToggle`) / `MachinePills`, `NeedsCount` / `DoneUnseenCount` / `HiddenNeedsBadge`, `Tag`, `StateBadge` / `StateDot` (a quiet Working session reads "Working · quiet 23m", counting up), `StateChip` (Needs you pulse + flash, glides between Phases; dimmed while its session is quiet), `FlowStrip` / `FlowCell` (cells never overflow: chips ellipsize and wrap to two lines), `Inbox` / `NeedsYouCard` / `DoneCard` / `InboxHeader`, `Split` (inbox beside the focus area), `Panel` / `SectionHeading` / `Eyebrow` / `Empty`, `PhaseTrack` / `PhaseName`, `GraphView` (one graph style for Spec DAGs, Maps with fog, to-tickets output), `TopBar`, `SessionTable` (one row per Tracked session: kind, "now: …" headline, time in state, "Working · quiet Nm" once it has had no events for the server's quiet threshold, 10 min by default, `factory server --quiet-minutes`; `SkillNote` for "running skill `<name>`" on ad hoc rows), `NowLine` ("now: …" headline), `SessionHeader` / `Timeline` / `Detail` / `Hint` and `AdHocView` (the ad hoc detail view: state, headline, last actions; other kinds use it, titled by kind, until their own view arrives), `TicketJobView` (Ticket, stage with a "duplicate of Job N" flag, branch, worktree, PR via `Facts` / `PrLink`, a "Mark abandoned" button while active, then last actions), `StepDetail` (one Step: Phase track and time in Phase, test pulse, files, commits, PR with CI checks, review findings, the agent's checklist and the struggle badge; in a Spec Job, Blocked by and no PR of its own) with `Review` / `StruggleTags`, `SpecJobView` (Spec, stage, integration branch, merged count, PR and whole-branch review; the Ticket DAG; the Step opened from the DAG or from its flow-strip chip), `WayfinderView` (the Map with its fog, Destination, the Decision ticket worked and its questions, tickets created and closed), `ResearchView` / `ToSpecView` / `ToTicketsView` (the planning sessions: question, searches, sources and findings; the Spec outline ticked as written; the Tickets created as a graph), `SoundToggle` (the header's sound on/off), `HistoryCount` / `HistoryList` (the header's History button and the ended Jobs with their outcome, each with a Replay button), `ReplayView` (a finished Job over time: play/pause, scrubber with event markers, each Step's `PhaseTrack` at that moment, the event list), and the unknown placeholders `Unknown` ("—"), `UnknownPhase`, `UnknownPhaseTag`, `StaleNote`.
- Pure helpers (`format.ts`, `flow.ts`, `graph.ts`, `inbox.ts`, `jobs.ts`, `replay.ts`, `specDag.ts`, `stepDetail.ts`, `wayfinder.ts`, `planning.ts`, `sounds.ts`, `machineFilter.ts`) are unit-tested with Vitest; components with behaviour of their own (`SpecJobView`) have a Testing Library test beside them.
- `src/gallery` shows every component in every state with fake data. Gallery-only layout lives in `gallery.css` and still uses tokens only.

Import everything from `src/ds` (its `index.ts` also loads the CSS).
