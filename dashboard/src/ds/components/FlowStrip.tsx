import { LayoutGroup } from "framer-motion";
import { FLOW_COLUMNS, flowColumn } from "../flow";
import { phaseClass } from "../format";
import type { Phase } from "../types";
import { StateChip, type StateChipProps } from "./StateChip";

export interface FlowRow {
  repo: string;
  chips: StateChipProps[];
}

/** The first and last columns are not Phases and have their own look. */
const edgeColumn = (i: number) => (i === 0 ? "fcol-unk" : i === FLOW_COLUMNS.length - 1 ? "fcol-plan" : null);

/** One row per Tracked repo, one column per Phase; chips glide between columns. */
export function FlowStrip({ rows }: { rows: FlowRow[] }) {
  return (
    <LayoutGroup>
      <section className="flow" aria-label="Flow strip — Steps by Phase">
        <div className="frow fhead">
          <div>Tracked repo</div>
          {FLOW_COLUMNS.map((c, i) => (
            <div key={c} className={edgeColumn(i) ?? phaseClass(c as Phase)} title={c}>{c}</div>
          ))}
        </div>
        {rows.map((r) => (
          <FlowStripRow key={r.repo} row={r} />
        ))}
      </section>
    </LayoutGroup>
  );
}

function FlowStripRow({ row }: { row: FlowRow }) {
  const cells = FLOW_COLUMNS.map(() => [] as StateChipProps[]);
  for (const c of row.chips) cells[flowColumn(c.phase === "planning" ? "planning" : { phase: c.phase })].push(c);
  return (
    <div className={`frow${row.chips.some((c) => c.state === "Needs you") ? " has-needs" : ""}`}>
      <div className="flabel">
        <span className="truncate mono" title={row.repo}>{row.repo}</span>
      </div>
      {cells.map((chips, i) => (
        <FlowCell key={FLOW_COLUMNS[i]} className={edgeColumn(i) ?? ""} chips={chips} />
      ))}
    </div>
  );
}

/** A cell never overflows: chips ellipsize and wrap to at most two lines. */
export function FlowCell({ chips, className = "" }: { chips: StateChipProps[]; className?: string }) {
  return (
    <div className={`fcell ${className}`}>
      {chips.map((c) => (
        <StateChip key={c.id} {...c} />
      ))}
    </div>
  );
}
