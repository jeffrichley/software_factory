import type { GraphNodeInput } from "./components/Graph";

/** The session kinds of research, to-spec and to-tickets sessions. */
export const RESEARCH = "research";
export const TO_SPEC = "to-spec";
export const TO_TICKETS = "to-tickets";

/** What a research session has read so far. */
export interface ResearchData {
  sessionId: string;
  /** The question asked (the skill's args); null when it was not given. */
  question: string | null;
  searches: string[];
  sources: string[];
  /** The findings file: its path in the repo and its link on GitHub (null outside the repo). */
  findings: { path: string; url: string | null } | null;
}

/** A section of to-spec's Spec template, and whether the session has written it. */
export interface OutlineSection {
  section: string;
  written: boolean;
}

/** What a to-spec session has written so far. */
export interface ToSpecData {
  sessionId: string;
  /** The Map it came from; null until known. */
  map: number | null;
  /** The Spec it published; null until published. */
  spec: number | null;
  outline: OutlineSection[];
}

/** A Ticket a to-tickets session created, as GitHub last had it (or as created, before a poll). */
export interface CreatedTicketData {
  number: number;
  /** null when neither the command nor a poll gave it. */
  title: string | null;
  url: string;
  state: "open" | "closed";
  /** The Tickets that block it. */
  blockedBy: number[];
}

/** What a to-tickets session has created so far. */
export interface ToTicketsData {
  sessionId: string;
  /** The Spec it breaks up; null until known. */
  spec: number | null;
  tickets: CreatedTicketData[];
}

export function createdTicketName(t: { number: number; title: string | null }): string {
  return t.title ? `#${t.number} ${t.title}` : `#${t.number}`;
}

/**
 * to-tickets output in the one graph grammar: each Ticket depends on the created Tickets that block it. No Ticket has a
 * Job yet, so every one is not started; those with no blocker are the frontier.
 */
export function ticketsGraph(tickets: CreatedTicketData[]): GraphNodeInput[] {
  const created = new Set(tickets.map((t) => t.number));
  return tickets.map((t) => ({
    id: String(t.number),
    deps: t.blockedBy.filter((n) => created.has(n)).map(String),
    resolved: false,
    body: { kind: "ticket", name: createdTicketName(t) },
  }));
}

/** How far a Spec outline is written: sections written of all, and the first one still to write (null when none is). */
export function outlineProgress(outline: OutlineSection[]): { written: number; total: number; current: number | null } {
  const current = outline.findIndex((o) => !o.written);
  return { written: outline.filter((o) => o.written).length, total: outline.length, current: current < 0 ? null : current };
}
