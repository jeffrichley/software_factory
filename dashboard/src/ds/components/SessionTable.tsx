import { formatDuration } from "../format";
import { AD_HOC, type SessionState } from "../types";
import { NowLine } from "./NowLine";
import { StateBadge } from "./StateBadge";
import { Empty } from "./Panel";

export interface SessionRowData {
  id: string;
  machine: string;
  repo: string;
  state: SessionState;
  /** Ticket Job, Spec Job, a planning kind (Wayfinder, to-spec, to-tickets, research) or ad hoc. */
  kind: string;
  /** The latest skill the skill table doesn't know, if any; an ad hoc row names it. */
  unknownSkill: string | null;
  /** The "now: …" headline; null until the session does something. */
  now: string | null;
  /** Done has been seen by the human. */
  seen?: boolean;
  /** ms the session has been in its state. */
  inStateMs: number;
}

/** "running skill `<name>`": how an ad hoc row names a skill the Factory doesn't know. */
export function SkillNote({ skill }: { skill: string }) {
  return <span className="tsub">running skill <code className="mono">{skill}</code></span>;
}

/** Tracked sessions, one row each, as variant E's session table shows them. Click a row for its detail. */
export function SessionTable({
  sessions, selectedId, onSelect,
}: { sessions: SessionRowData[]; selectedId?: string; onSelect?: (id: string) => void }) {
  if (!sessions.length) return <Empty>No Tracked sessions yet. Start Claude Code in a Tracked repo.</Empty>;
  return (
    <table className="tri">
      <colgroup><col className="c-state" /><col className="c-mach" /><col className="c-repo" /><col className="c-kind" /><col /><col className="c-time" /></colgroup>
      <thead>
        <tr><th>State</th><th>Machine</th><th>Tracked repo</th><th>Kind</th><th>Headline</th><th>In state</th></tr>
      </thead>
      <tbody>
        {sessions.map((s) => (
          <tr
            key={s.id}
            className={`row${s.id === selectedId ? " sel" : ""}`}
            tabIndex={onSelect ? 0 : undefined}
            aria-label={`${s.state}: ${s.kind} session in ${s.repo} on ${s.machine}`}
            onClick={onSelect ? () => onSelect(s.id) : undefined}
            onKeyDown={onSelect ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(s.id); } } : undefined}
          >
            <td><StateBadge state={s.state} seen={s.seen} /></td>
            <td className="mono">{s.machine}</td>
            <td className="mono">{s.repo}</td>
            <td>{s.kind}{s.kind === AD_HOC && s.unknownSkill ? <SkillNote skill={s.unknownSkill} /> : null}</td>
            <td><NowLine now={s.now} /></td>
            <td><span className="tmain">{formatDuration(s.inStateMs)}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
