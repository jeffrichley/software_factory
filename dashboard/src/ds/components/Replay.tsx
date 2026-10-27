import { useEffect, useState } from "react";
import type { JobData } from "../jobs";
import { formatOffset, MARKED_KINDS, replayFrame, replayLength, type ReplayData } from "../replay";
import { PENDING, type Phase } from "../types";
import { Icon } from "./Icon";
import { WorkItemLink } from "./InboxCards";
import { Eyebrow, Panel } from "./Panel";
import { PhaseTrack } from "./PhaseTrack";
import { Hint, PrLink } from "./SessionDetail";
import { Tag } from "./Tag";

/** How many ticks a full play takes, whatever the Job's length (variant E: 120 ticks of 100 ms). */
const PLAY_TICKS = 120;
const TICK_MS = 100;

const KIND_LABEL: Record<string, string> = {
  start: "Job started", phase: "Phase change", action: "Action", test_pass: "Tests pass", test_fail: "Tests fail",
  commit: "Commit", review: "Review", needs: "Needs you", pr: "PR", end: "Job ended",
};

/** The legend's marker kinds, in variant E's order. */
const LEGEND = ["phase", "test_pass", "test_fail", "commit", "needs", "review", "end"] as const;

function Marker({ kind }: { kind: string }) {
  return <span className={`mk-i mk-${kind}`} aria-hidden="true" />;
}

function stepName(s: ReplayData["steps"][number]): string {
  return [s.number ? `#${s.number}` : null, s.title].filter(Boolean).join(" ") || "Step";
}

export interface ReplayViewProps {
  job: JobData;
  /** The Job's timeline; null while it loads. */
  replay: ReplayData | null;
  /** Back to the History list. */
  onBack: () => void;
  /** Where the scrubber starts, in seconds since the Job started (the gallery shows a moment mid-Job). */
  initialPos?: number;
}

/** A finished Job replayed: play/pause and a scrubber with its events marked, each Step's Phase then, and the events. */
export function ReplayView({ job, replay, onBack, initialPos = 0 }: ReplayViewProps) {
  const [pos, setPos] = useState(initialPos);
  const [playing, setPlaying] = useState(false);
  const length = replay ? replayLength(replay) : 1;
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      setPos((p) => {
        const next = Math.min(length, p + length / PLAY_TICKS);
        if (next >= length) setPlaying(false);
        return next;
      });
    }, TICK_MS);
    return () => clearInterval(timer);
  }, [playing, length]);
  const seek = (t: number) => {
    setPlaying(false);
    setPos(t);
  };
  const togglePlay = () => {
    if (!playing && pos >= length) setPos(0);
    setPlaying(!playing);
  };
  const title = job.workItem ? <WorkItemLink item={job.workItem} /> : job.number ? `#${job.number}` : "Job " + job.id;
  const frame = replay ? replayFrame(replay, pos) : null;
  const current = replay && frame && frame.current >= 0 ? replay.events[frame.current] : null;
  return (
    <section className="detail" aria-label="Replay">
      <nav className="crumbs" aria-label="Zoom level">
        <span>Overview</span><span aria-hidden="true">›</span>
        <button type="button" className="crumb-btn" onClick={onBack}>History</button><span aria-hidden="true">›</span>
        <span className="cur">Replay</span>
      </nav>
      <header className="sd-h">
        <Eyebrow>{job.kind} · Replay</Eyebrow>
        <h2>{title}</h2>
        <div className="sd-meta">
          <Tag tone={job.stage === "Merged" ? "plain" : "unknown"}>{job.stage}</Tag>
          <span>PR <PrLink pr={job.pr} /></span>
          <span>repo <span className="mono">{job.repo}</span></span>
          <span className="mono">{job.machine}</span>
          {replay ? <span>took {formatOffset(length)}</span> : null}
        </div>
      </header>
      {replay && frame ? (
        <>
          <div className="rp-ctl">
            <button type="button" className="btn btn-icon" aria-pressed={playing} aria-label={`${playing ? "Pause" : "Play"} replay`} onClick={togglePlay}>
              <Icon name={playing ? "pause" : "play"} size="18px" />
            </button>
            <div className="rp-track">
              <div className="scrub">
                {replay.events.map((e, i) =>
                  (MARKED_KINDS as readonly string[]).includes(e.kind) ? (
                    <button
                      key={i}
                      type="button"
                      className={`mk mk-${e.kind}`}
                      style={{ left: `${((e.t / length) * 100).toFixed(2)}%` }}
                      title={`${formatOffset(e.t)} · ${e.text}`}
                      aria-label={`${formatOffset(e.t)} ${e.text}`}
                      onClick={() => seek(e.t)}
                    />
                  ) : null,
                )}
              </div>
              <input type="range" min={0} max={length} step={1} value={Math.round(pos)} aria-label="Scrub replay timeline"
                onChange={(e) => seek(Number(e.target.value))} />
            </div>
            <span className="rp-time">{formatOffset(pos)} / {formatOffset(length)}</span>
          </div>
          <div className="rp-legend">
            {LEGEND.map((k) => <span key={k}><Marker kind={k} />{KIND_LABEL[k]}</span>)}
          </div>
          <div className="rp-grid">
            <Panel title={`Phase at ${formatOffset(pos)}`}>
              {replay.steps.length ? replay.steps.map((s) => (
                <div key={s.id} className="rp-step">
                  {replay.steps.length > 1 ? <span className="rp-step-name">{stepName(s)}</span> : null}
                  {frame.phases[s.id] === PENDING ? <Tag tone="unknown">Pending</Tag> : <PhaseTrack phase={frame.phases[s.id] as Phase | null} />}
                </div>
              )) : <Hint>This Job has no Steps.</Hint>}
            </Panel>
            <Panel title="Event">
              {current ? (
                <div className="rp-ev">
                  <Marker kind={current.kind} />
                  <div>
                    <Eyebrow>{formatOffset(current.t)} · {KIND_LABEL[current.kind] ?? current.kind}</Eyebrow>
                    <p>{current.text}</p>
                  </div>
                </div>
              ) : <Hint>Nothing has happened yet.</Hint>}
            </Panel>
          </div>
          <Panel title={`Events · ${replay.events.length}`}>
            <ol className="rp-list">
              {replay.events.map((e, i) => (
                <li key={i}>
                  <button type="button" className={`rp-li${i < frame.current ? " past" : i === frame.current ? " cur" : ""}`}
                    aria-current={i === frame.current ? "step" : undefined} onClick={() => seek(e.t)}>
                    <time>{formatOffset(e.t)}</time>
                    <Marker kind={e.kind} />
                    <span>{e.text}</span>
                  </button>
                </li>
              ))}
            </ol>
          </Panel>
        </>
      ) : (
        <Hint>Loading the Job’s timeline…</Hint>
      )}
    </section>
  );
}
