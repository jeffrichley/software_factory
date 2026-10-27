import type { SessionState } from "./types";

interface InboxSession {
  state: SessionState;
  seen: boolean;
}

/** The left panel's two lists, in the order given (the server sends Needs you longest waiting first). */
export function inboxOf<S extends InboxSession>(sessions: S[]): { needs: S[]; doneUnseen: S[] } {
  return {
    needs: sessions.filter((s) => s.state === "Needs you"),
    doneUnseen: sessions.filter((s) => s.state === "Done" && !s.seen),
  };
}

/** What the human types to get back into a Claude Code session. */
export function resumeCommand(ccSessionId: string): string {
  return `claude --resume ${ccSessionId}`;
}
