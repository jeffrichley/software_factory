import { formatClock } from "../format";
import type { JobData } from "../jobs";
import { Icon } from "./Icon";
import { WorkItemLink } from "./InboxCards";
import { Empty, Eyebrow, Panel } from "./Panel";
import { Detail, Hint, PrLink } from "./SessionDetail";
import { Tag } from "./Tag";

/** The header's History button (variant E's), with how many Jobs have ended; opens the History list. */
export function HistoryCount({ count, open, onToggle }: { count: number; open: boolean; onToggle: () => void }) {
  return (
    <button type="button" className={`btn${open ? " btn-on" : ""}`} aria-pressed={open} onClick={onToggle}>
      <Icon name="history" />
      History<b className="btn-count">{count}</b>
    </button>
  );
}

/** Ended Jobs (Merged, Closed, Abandoned), each with its outcome, Work item, repo, Machine, PR and start time, and a Replay. */
export function HistoryList({ jobs, onReplay }: { jobs: JobData[]; onReplay?: (jobId: string) => void }) {
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
      <Panel title={`Ended Jobs · ${jobs.length}`}>
        {jobs.length ? (
          <ul className="hist">
            {jobs.map((j) => (
              <li key={j.id}>
                <Tag tone={j.stage === "Merged" ? "plain" : "unknown"}>{j.stage}</Tag>
                <span className="hist-item">
                  {j.workItem ? <WorkItemLink item={j.workItem} /> : j.number ? <span className="mono">#{j.number}</span> : <WorkItemLink item={null} />}
                </span>
                <span className="mono hist-meta">{j.repo}</span>
                <span className="mono hist-meta">{j.machine}</span>
                <span className="hist-meta">{j.kind} {j.id}</span>
                <span className="hist-meta">PR <PrLink pr={j.pr} /></span>
                <time className="hist-meta" dateTime={j.startedAt}>started {formatClock(j.startedAt)}</time>
                {onReplay ? (
                  <button type="button" className="btn" onClick={() => onReplay(j.id)}><Icon name="play" />Replay</button>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <Empty>No Job has ended yet. Merged, Closed and Abandoned Jobs land here.</Empty>
        )}
      </Panel>
    </Detail>
  );
}
