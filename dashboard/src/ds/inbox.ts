import type { SessionState } from "./types";

interface InboxSession {
  state: SessionState;
  /** ISO time the session entered its state. */
  state_since: string;
  seen: boolean;
}

/** The left panel's two lists: the Needs you inbox, longest waiting first, then Done-unseen, latest first. */
export function inboxOf<S extends InboxSession>(sessions: S[]): { needs: S[]; doneUnseen: S[] } {
  const since = (s: S) => Date.parse(s.state_since);
  return {
    needs: sessions.filter((s) => s.state === "Needs you").sort((a, b) => since(a) - since(b)),
    doneUnseen: sessions.filter((s) => s.state === "Done" && !s.seen).sort((a, b) => since(b) - since(a)),
  };
}

/** What the human types to get back into a Claude Code session. */
export function resumeCommand(ccSessionId: string): string {
  return `claude --resume ${ccSessionId}`;
}
