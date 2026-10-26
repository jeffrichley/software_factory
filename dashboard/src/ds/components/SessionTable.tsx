import { formatDuration } from "../format";
import type { SessionState } from "../types";
import { StateBadge } from "./StateBadge";
import { Empty } from "./Panel";

export interface SessionRowData {
  id: string;
  machine: string;
  repo: string;
  state: SessionState;
  /** ms the session has been in its state. */
  inStateMs: number;
}

/** Tracked sessions, one row each, as variant E's session table shows them. */
export function SessionTable({ sessions }: { sessions: SessionRowData[] }) {
  if (!sessions.length) return <Empty>No Tracked sessions yet. Start Claude Code in a Tracked repo.</Empty>;
  return (
    <table className="tri">
      <colgroup><col className="c-state" /><col className="c-mach" /><col /><col className="c-time" /></colgroup>
      <thead>
        <tr><th>State</th><th>Machine</th><th>Tracked repo</th><th>In state</th></tr>
      </thead>
      <tbody>
        {sessions.map((s) => (
          <tr key={s.id} aria-label={`${s.state}: ${s.repo} on ${s.machine}`}>
            <td><StateBadge state={s.state} /></td>
            <td className="mono">{s.machine}</td>
            <td className="mono">{s.repo}</td>
            <td><span className="tmain">{formatDuration(s.inStateMs)}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
