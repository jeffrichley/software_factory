import { currentJob, isEnded } from "./jobs";
import { SPEC_JOB, type SessionState } from "./types";

interface SelectableSession {
  id: string;
  kind: string;
  state: SessionState;
}

/**
 * The session the centre shows, as in variant E: the one the human opened while it is still on show (or hidden by the
 * human since, so its Show button stays at hand; `hidden` = the hidden sessions on shown Machines); else a Spec
 * Job with an active Job, else the first Needs you (in the order given), else the session started last (session ids grow).
 */
export function selectedSessionOf<S extends SelectableSession>(
  sessions: S[],
  jobs: { id: string; sessionId: string; stage: string }[],
  openedId: string | undefined,
  hidden: S[] = [],
): S | null {
  const opened = [...sessions, ...hidden].find((s) => s.id === openedId);
  if (opened) return opened;
  const spec = sessions.find((s) => {
    const job = s.kind === SPEC_JOB ? currentJob(jobs, s.id) : null;
    return job !== null && !isEnded(job.stage);
  });
  if (spec) return spec;
  const needs = sessions.find((s) => s.state === "Needs you");
  if (needs) return needs;
  return sessions.reduce<S | null>((latest, s) => (!latest || Number(s.id) > Number(latest.id) ? s : latest), null);
}
