import { formatClock } from "../format";
import type { JobData } from "../jobs";
import { Icon } from "./Icon";
import { WorkItemLink } from "./InboxCards";
import { Empty, Panel } from "./Panel";
import { PrLink } from "./SessionDetail";
import { Tag } from "./Tag";

/** The header's History button: how many Jobs have ended; opens the History list. */
export function HistoryCount({ count, open, onToggle }: { count: number; open: boolean; onToggle: () => void }) {
  return (
    <button type="button" className={`count count-history${open ? " on" : ""}`} aria-pressed={open} onClick={onToggle}>
      <Icon name="clock" />
      <b>{count}</b>History
    </button>
  );
}

/** Ended Jobs (Merged, Closed, Abandoned), each with its outcome, Work item, repo, Machine, PR and start time, and a Replay. */
export function HistoryList({ jobs, onReplay }: { jobs: JobData[]; onReplay?: (jobId: string) => void }) {
  return (
    <Panel title={`History · ${jobs.length}`} label="History">
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
  );
}
