import { endedJob, type JobData } from "../jobs";
import { Icon } from "./Icon";
import { Empty, Eyebrow, Panel } from "./Panel";
import { RepoName } from "./RepoName";
import { Detail, Hint } from "./SessionDetail";
import { Unknown } from "./Unknown";

/** The header's History button: how many Jobs have ended; opens the History list. */
export function HistoryCount({ count, open, onToggle }: { count: number; open: boolean; onToggle: () => void }) {
  return (
    <button type="button" className={`count count-history${open ? " on" : ""}`} aria-pressed={open} onClick={onToggle}>
      <Icon name="clock" />
      <b>{count}</b>History
    </button>
  );
}

/** Ended Jobs (Merged, Closed, Abandoned), as variant E's rows: outcome and PR, Work item, kind · repo · Machine, how long
 * it took and how long ago it ended; picking one replays it. */
export function HistoryList({ jobs, nowMs, onReplay }: { jobs: JobData[]; nowMs: number; onReplay?: (jobId: string) => void }) {
  return (
    <Detail label="History">
      <nav className="crumbs" aria-label="Zoom level">
        <span>Overview</span><span aria-hidden="true">›</span><span className="cur">History</span>
      </nav>
      <header className="sd-h">
        <Eyebrow>History</Eyebrow>
        <h2>Finished Jobs</h2>
        <Hint>Pick a Job to replay its events.</Hint>
      </header>
      {jobs.length ? (
        <ul className="hlist" aria-label={`Ended Jobs · ${jobs.length}`}>
          {jobs.map((j) => {
            const e = endedJob(j, nowMs);
            const name = j.workItem?.name ?? (j.number ? `#${j.number}` : `${j.kind} ${j.id}`);
            return (
              <li key={j.id}>
                <button type="button" className="hrow" onClick={() => onReplay?.(j.id)} aria-label={`Replay ${name} — ${e.outcome}`}>
                  <span className={`hout out-${e.tone}`}>
                    <Icon name={e.icon} />{e.outcome}{j.pr?.number ? <span className="mono">#{j.pr.number}</span> : null}
                  </span>
                  <span className="hname">
                    <span className="ht truncate" title={name}>{name}</span>
                    <span className="hm truncate">{j.kind} · <RepoName repo={j.repo} /> · {j.machine}</span>
                  </span>
                  <span className="hdur" title="How long it took">{e.took ?? <Unknown />}</span>
                  <span className="hago">{j.endedAt ? <time dateTime={j.endedAt}>{e.ago}</time> : <Unknown />}</span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <Panel title="Ended Jobs · 0">
          <Empty>No Job has ended yet. Merged, Closed and Abandoned Jobs land here.</Empty>
        </Panel>
      )}
    </Detail>
  );
}
