import { currentJob, isEnded } from "./jobs";
import { SPEC_JOB, type SessionState } from "./types";

interface SelectableSession {
  id: string;
  kind: string;
  state: SessionState;
  /** ms the session has been in its state. */
  inStateMs: number;
}

/**
 * The session the centre shows, as in variant E: the one the human opened while it is still on show; else a Spec
 * Job with an active Job, else the first Needs you (in the order given), else the session that changed state last.
 */
export function selectedSessionOf<S extends SelectableSession>(
  sessions: S[],
  jobs: { id: string; sessionId: string; stage: string }[],
  openedId: string | undefined,
): S | null {
  const opened = sessions.find((s) => s.id === openedId);
  if (opened) return opened;
  const spec = sessions.find((s) => {
    const job = s.kind === SPEC_JOB ? currentJob(jobs, s.id) : null;
    return job !== null && !isEnded(job.stage);
  });
  if (spec) return spec;
  const needs = sessions.find((s) => s.state === "Needs you");
  if (needs) return needs;
  return sessions.reduce<S | null>((latest, s) => (!latest || s.inStateMs < latest.inStateMs ? s : latest), null);
}
