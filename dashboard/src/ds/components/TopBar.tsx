import type { ReactNode } from "react";

/** The dashboard's sticky header: brand on the left, then whatever the screen puts in it. */
export function TopBar({ children }: { children?: ReactNode }) {
  return (
    <header className="top">
      <div className="brand"><span className="brand-mark" aria-hidden="true" />Factory</div>
      {children}
    </header>
  );
}
