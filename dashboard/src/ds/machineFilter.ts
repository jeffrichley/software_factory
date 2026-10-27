import type { SessionState } from "./types";

/**
 * The Machine filter: Machine pills toggle Machines off and on. It is remembered in the browser (the Machines
 * hidden) and in ?machines= (the Machines shown); the URL wins, so a shared link shows the same view.
 */

/** Where the browser remembers the Machines hidden. */
export const HIDDEN_MACHINES_KEY = "factory.hiddenMachines";

/** The Machines hidden, from the page's query string (?machines= names those shown) or else what the browser remembers. */
export function hiddenMachinesOf(names: string[], search: string, remembered: string[]): string[] {
  const shown = new URLSearchParams(search).get("machines");
  if (shown !== null) {
    const on = shown.split(",").filter(Boolean);
    return names.filter((n) => !on.includes(n));
  }
  return names.filter((n) => remembered.includes(n));
}

/** The page's URL with ?machines= naming the Machines shown, or without it when none are hidden. */
export function filterUrl(href: string, names: string[], hidden: string[]): string {
  const url = new URL(href);
  if (hidden.length) url.searchParams.set("machines", names.filter((n) => !hidden.includes(n)).join(","));
  else url.searchParams.delete("machines");
  return url.toString();
}

interface FilteredSession {
  machine: string;
  state: SessionState;
  /** Hidden by the human (/factory:hide or the dashboard). */
  hidden: boolean;
}

/**
 * What the dashboard shows under the filter. A hidden Machine drops out of every view, but its Needs you still
 * counts towards the "+N Needs you on hidden Machines" badge; a hidden session drops out of everything, badge too.
 */
export function viewOf<S extends FilteredSession>(sessions: S[], hiddenMachines: string[]) {
  const onShownMachine = sessions.filter((s) => !hiddenMachines.includes(s.machine));
  return {
    shown: onShownMachine.filter((s) => !s.hidden),
    hiddenSessions: onShownMachine.filter((s) => s.hidden),
    hiddenNeeds: sessions.filter((s) => !s.hidden && s.state === "Needs you" && hiddenMachines.includes(s.machine)),
  };
}
