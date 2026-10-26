# Factory dashboard

React + TypeScript + Vite. Look and behaviour follow prototype variant E (branch `prototype/dashboard`, `?variant=E`).

```sh
npm install
npm run dev        # http://localhost:5173 — the design-system gallery (?theme=light|dark)
npm run typecheck
npm test
```

## Design system (`src/ds`)

**Rule: the dashboard UI is built only from the design system's tokens and components. No one-off styling** — no raw colours, sizes, radii or timings, and no component-local CSS outside `src/ds`. Inside `src/ds`, colours, type, spacing, radii and motion come from `tokens.css`; a component's own fixed geometry (a 7px dot, an 18px badge) may stay literal in `components.css`. If a screen needs something the system lacks, add it to `src/ds` (token, component or variant), show it in the gallery in every state, and check it against variant E.

- `tokens.css` — colour roles written once as `light-dark(light, dark)` (dark = variant E, light derived; follows the OS unless `<html data-theme>` overrides), type scale, spacing, radii, motion. `motion.ts` mirrors the motion tokens for Framer Motion.
- Components: `MachinePill`, `NeedsCount` / `DoneUnseenCount` / `HiddenNeedsBadge`, `Tag`, `StateBadge` / `StateDot`, `StateChip` (Needs you pulse + flash, glides between Phases), `FlowStrip` / `FlowCell` (cells never overflow: chips ellipsize and wrap to two lines), `NeedsYouCard` / `DoneCard` / `InboxHeader`, `Panel` / `SectionHeading` / `Eyebrow` / `Empty`, `PhaseTrack` / `PhaseName`, `GraphView` (one graph style for Spec DAGs, Maps with fog, to-tickets output), and the unknown placeholders `Unknown` ("—"), `UnknownPhase`, `UnknownPhaseTag`, `StaleNote`.
- Pure helpers (`format.ts`, `flow.ts`, `graph.ts`) are unit-tested with Vitest.
- `src/gallery` shows every component in every state with fake data. Gallery-only layout lives in `gallery.css` and still uses tokens only.

Import everything from `src/ds` (its `index.ts` also loads the CSS).
