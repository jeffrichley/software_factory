import { type ReactNode, useEffect, useRef } from "react";
import { Icon, type IconName } from "./Icon";

export function Panel({ title, children, label }: { title?: ReactNode; children: ReactNode; label?: string }) {
  return (
    <div className="panel" aria-label={label}>
      {title ? <h4>{title}</h4> : null}
      {children}
    </div>
  );
}

export function SectionHeading({ children, icon, tone }: { children: ReactNode; icon?: IconName; tone?: "done" | "needs" }) {
  return (
    <h3 className={`sec-h${tone ? ` tone-${tone}` : ""}`}>
      {icon ? <Icon name={icon} /> : null}
      {children}
    </h3>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <span className="eyebrow">{children}</span>;
}

/**
 * Variant E's body: the flow strip full width on top, then a fixed-width left panel (the inbox) beside the focus
 * area (the centre); on a wide screen the inbox and the centre each scroll on their own.
 */
export function Split({ top, side, children, view }: {
  top?: ReactNode;
  side: ReactNode;
  children: ReactNode;
  /** What the centre shows (a session, History, a Replay); when it changes the centre scrolls back to the top. */
  view?: string;
}) {
  const main = useRef<HTMLElement>(null);
  useEffect(() => {
    main.current?.scrollTo?.(0, 0);
  }, [view]);
  return (
    <main className="split">
      {top ?? <div />}
      <div className="split-body">
        {side}
        <section className="split-main" aria-label="Focus" ref={main}>{children}</section>
      </div>
    </main>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
