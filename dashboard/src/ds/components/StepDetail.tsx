import { formatClock, formatDuration } from "../format";
import { ticketName } from "../specDag";
import {
  currentItem,
  diffBlocks,
  phaseChange,
  struggleLabels,
  type CheckData,
  type StepDetailData,
  type StruggleData,
} from "../stepDetail";
import type { MergeData } from "../specJob";
import { PENDING, type StepPhase } from "../types";
import { Icon, type IconName } from "./Icon";
import { Eyebrow, Panel } from "./Panel";
import { PhaseTrack } from "./PhaseTrack";
import { Tag } from "./Tag";
import { Unknown } from "./Unknown";

/** A Step as its detail needs it. */
export interface StepData {
  number: number | null;
  title: string | null;
  phase: StepPhase;
  phaseSince: string;
}

export interface StepDetailProps {
  step: StepData;
  /** What the Step has done; null before the server has any detail for it. */
  detail: StepDetailData | null;
  nowMs: number;
  /** A Spec Job's Step merges into the integration branch rather than ending as a PR. */
  inSpecJob?: boolean;
  /** The Tickets blocking it, by name. */
  blockers?: string[];
  /** A Spec Job's integration branch, which its Steps merge into. */
  integrationBranch?: string | null;
}

/** The struggle badge: one tag per reason a Step looks stuck. */
export function StruggleTags({ struggle }: { struggle: StruggleData | null }) {
  const labels = struggleLabels(struggle);
  if (!labels.length) return null;
  return (
    <span className="struggle">
      {labels.map((l, i) => (
        <Tag key={l} tone="struggle">{i === 0 && struggle?.failures ? <Icon name="flame" /> : null}{l}</Tag>
      ))}
    </span>
  );
}

/** Everything about a Step needed to judge its progress: Phase track, checklist, tests, files, commits, review and PR. */
export function StepDetail({ step, detail, nowMs, inSpecJob, blockers = [], integrationBranch = null }: StepDetailProps) {
  return (
    <section className="step" aria-label="Step detail">
      <div className="step-h">
        <div>
          <Eyebrow>{inSpecJob ? "Step · Ticket" : "Step"}</Eyebrow>
          <h3>{ticketName(step)}</h3>
        </div>
        <div className="step-tags">
          <StruggleTags struggle={detail?.struggle ?? null} />
          {blockers.length ? <Tag tone="blocked">Blocked by {blockers.join(", ")}</Tag> : null}
        </div>
      </div>
      {step.phase === PENDING ? <Tag tone="unknown">Pending</Tag> : <PhaseTrack phase={step.phase} />}
      {step.phase && step.phase !== PENDING ? (
        <p className="phase-time">In {step.phase} for {formatDuration(nowMs - Date.parse(step.phaseSince))}</p>
      ) : null}
      <div className="step-grid">
        <Panel title="Agent checklist (live)"><Checklist items={detail?.checklist ?? null} /></Panel>
        <Panel title="Tests">
          <TestsPulse tests={detail?.tests ?? null} />
          <h4>Files touched</h4>
          <Files files={detail?.files ?? []} churn={detail?.struggle?.churn ?? []} />
        </Panel>
        <Commits commits={detail?.commits ?? []} />
        <Panel title="Review findings">
          <Review review={detail?.review ?? null} />
          {inSpecJob ? <MergeNote phase={step.phase} merge={detail?.merge ?? null} branch={integrationBranch} nowMs={nowMs} /> : <PullRequest pr={detail?.pr ?? null} />}
        </Panel>
      </div>
      <Panel title="Phase events">
        {detail?.phaseEvents.length ? (
          <ol className="events">
            {[...detail.phaseEvents].reverse().map((e, i) => (
              <li key={`${e.at}-${i}`}><time dateTime={e.at}>{formatClock(e.at)}</time><span>{phaseChange(e)}</span></li>
            ))}
          </ol>
        ) : <p className="hint">No Phase changes yet.</p>}
      </Panel>
    </section>
  );
}

function Checklist({ items }: { items: StepDetailData["checklist"] }) {
  if (items === null) return <Unknown />;
  if (!items.length) return <p className="hint">The checklist is empty.</p>;
  const cur = currentItem(items);
  return (
    <ul className="checklist">
      {items.map((item, i) => {
        const done = item.status === "completed";
        return (
          <li key={`${item.text}-${i}`} className={done ? "done" : i === cur ? "cur" : undefined}>
            <span className="cb" aria-label={done ? "done" : "not done"}>{done ? <Icon name="check" size="12px" /> : null}</span>
            <span>{item.text}</span>
          </li>
        );
      })}
    </ul>
  );
}

function TestsPulse({ tests }: { tests: StepDetailData["tests"] }) {
  if (!tests) return <p className="hint">No test runs yet.</p>;
  const failing = tests.last === "fail";
  const counts = tests.passed === null ? "no summary line" : `${tests.passed} passed · ${tests.failed} failed`;
  return (
    <div className="tests">
      <span className={`tpulse ${failing ? "fail" : "pass"}`} aria-hidden="true" />
      <span className={failing ? "lbl-fail" : "lbl-pass"}>{failing ? "Failing" : "Passing"}</span>
      <span className="mono">{counts}</span>
      <span className="thist" aria-label={`Last ${tests.runs.length} runs`}>
        {tests.runs.map((r, i) => <i key={`${r.at}-${i}`} className={r.result === "fail" ? "f" : "p"} />)}
      </span>
    </div>
  );
}

function Files({ files, churn }: { files: StepDetailData["files"]; churn: string[] }) {
  if (!files.length) return <p className="hint">No files changed yet.</p>;
  return (
    <ul className="files">
      {files.map((f) => (
        <li key={f.path}>
          <span className="path">{f.path}</span>
          <span className={`mono ${churn.includes(f.path) ? "churn" : "muted"}`}>{f.edits} {f.edits === 1 ? "edit" : "edits"}</span>
          {f.added === null || f.deleted === null ? <Unknown /> : (
            <>
              <span className="add">+{f.added}</span>
              <span className="del">−{f.deleted}</span>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}

function Commits({ commits }: { commits: StepDetailData["commits"] }) {
  const added = commits.reduce((n, c) => n + c.added, 0);
  const deleted = commits.reduce((n, c) => n + c.deleted, 0);
  return (
    <Panel title={<>Commits{commits.length ? <> · <span className="add">+{added}</span> <span className="del">−{deleted}</span></> : null}</>}>
      {commits.length ? (
        <ul className="commits">
          {commits.map((c) => (
            <li key={c.sha}>
              <span className="sha">{c.sha}</span>
              <span className="msg">{c.message}</span>
              <span className="add">+{c.added}</span>
              <span className="del">−{c.deleted}</span>
              <span className="dstat" aria-hidden="true">{diffBlocks(c.added, c.deleted).map((b, i) => <i key={i} className={b || undefined} />)}</span>
            </li>
          ))}
        </ul>
      ) : <p className="hint">No commits yet.</p>}
    </Panel>
  );
}

export function Review({ review }: { review: StepDetailData["review"] }) {
  if (!review) return <p className="hint">Not reviewed yet.</p>;
  return (
    <div className="review">
      <span className="big-num">{review.standards + review.spec}</span>
      <span className="hint">
        {review.standards} Standards · {review.spec} Spec{review.source === "summary" ? " (read from the review’s summary)" : ""}
      </span>
    </div>
  );
}

const CHECK: Record<CheckData["status"], [IconName, string]> = {
  pass: ["check", "passed"],
  fail: ["alert", "failed"],
  pending: ["clock", "pending"],
  skipped: ["arrow", "skipped"],
};

function PullRequest({ pr }: { pr: StepDetailData["pr"] }) {
  if (!pr) return <><h4>Pull request</h4><p className="hint">No PR yet.</p></>;
  return (
    <>
      <h4>Pull request</h4>
      <div className="pr-line">
        <a className="wi mono" href={pr.url}>{pr.number ? `PR #${pr.number}` : pr.url}</a>
        {pr.draft ? <Tag tone="unknown">draft</Tag> : null}
      </div>
      <h4>CI checks</h4>
      <Checks checks={pr.checks} />
    </>
  );
}

/** A PR's CI checks, each passed, failed, pending or skipped; unknown until read. */
export function Checks({ checks }: { checks: CheckData[] | null }) {
  if (checks === null) return <Unknown />;
  if (!checks.length) return <p className="hint">No CI checks on this PR.</p>;
  return (
    <ul className="checks">
      {checks.map((c) => (
        <li key={c.name} className={`chk-${c.status}`}>
          <Icon name={CHECK[c.status][0]} />
          <span className="mono">{c.name}</span>
          <span>{CHECK[c.status][1]}</span>
        </li>
      ))}
    </ul>
  );
}

function MergeNote({ phase, merge, branch, nowMs }: { phase: StepPhase; merge: MergeData | null; branch: string | null; nowMs: number }) {
  const into = branch ? <span className="mono">{branch}</span> : "the integration branch";
  return (
    <>
      <h4>Merge into integration branch</h4>
      {merge || phase === "Merged" ? (
        <p className="hint merged-note">
          <Icon name="check" /> Merged into {into}
          {merge ? <> · {merge.sha ? <span className="sha">{merge.sha}</span> : <Unknown />} · {formatDuration(nowMs - Date.parse(merge.at))} ago</> : null}
        </p>
      ) : <p className="hint">Not merged yet: merges into {into} after Committed.</p>}
    </>
  );
}
