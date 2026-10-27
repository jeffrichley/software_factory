import type { ReactNode } from "react";
import { formatClock } from "../format";
import { ticketName } from "../specDag";
import type { MergeEntry, PrTrackStage } from "../specJob";
import { Icon } from "./Icon";
import { Unknown } from "./Unknown";

/** One stat tile: a small label over a value, as variant E heads a Spec Job. */
export function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="stat" role="group" aria-label={label}>
      <span className="eyebrow">{label}</span>
      <span className="stat-v">{children}</span>
    </div>
  );
}

/** A row of stat tiles (four across, two on a phone). */
export function StatTiles({ children }: { children: ReactNode }) {
  return <div className="stats">{children}</div>;
}

/** A PR's track Draft → Ready → Merged: the stages reached, with when, and the one it is in now. */
export function PrTrack({ stages }: { stages: PrTrackStage[] }) {
  const current = stages.find((s) => s.status === "current")?.stage ?? "unknown";
  return (
    <ol className="prtrack" aria-label={`PR state: ${current}`}>
      {stages.map((s) => (
        <li key={s.stage} className={`pt-${s.status}`} aria-current={s.status === "current" ? "step" : undefined}>
          {s.stage}
          {s.at ? <> <time dateTime={s.at}>{formatClock(s.at)}</time></> : null}
        </li>
      ))}
    </ol>
  );
}

/** The Tickets merged into a Spec Job's integration branch, each with its merge SHA, and how many are left. */
export function Merges({ branch, merges, total }: { branch: string | null; merges: MergeEntry[]; total: number }) {
  const left = total - merges.length;
  const title = `Merges into ${branch ?? "the integration branch"}`;
  return (
    <section className="panel" aria-label={title}>
      <h4>{title}</h4>
      {merges.length ? (
        <ul className="merges">
          {merges.map((m) => (
            <li key={m.step.id}>
              <span className="merged-mark"><Icon name="check" /></span>
              <span className="merge-t">{ticketName(m.step)}</span>
              {m.sha ? <span className="sha">{m.sha}</span> : <Unknown />}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="hint">{!total ? "No Tickets yet." : left ? `${left} ${left === 1 ? "Ticket" : "Tickets"} not yet merged.` : "Every Ticket is merged."}</p>
    </section>
  );
}
