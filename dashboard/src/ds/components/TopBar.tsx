import type { ReactNode } from "react";
import { formatWallClock } from "../format";

/** The dashboard's sticky header: brand on the left, then whatever the screen puts in it. */
export function TopBar({ children }: { children?: ReactNode }) {
  return (
    <header className="top">
      <div className="brand"><span className="brand-mark" aria-hidden="true" />Factory</div>
      {children}
    </header>
  );
}

/** The header clock (variant E's): local time to the second; hidden below 1440px, as in E. */
export function Clock({ now }: { now: number }) {
  return <time className="clock" dateTime={new Date(now).toISOString()}>{formatWallClock(now)}</time>;
}
